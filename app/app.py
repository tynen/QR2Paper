

import os
import io
import logging
import json
import traceback
import secrets
from flask import Flask, render_template, request, flash, redirect
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from PIL import Image
import cups

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_urlsafe(64))
logger = logging.getLogger("qr_print_app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SETTINGS_FILE = "printer_settings.json"

# Global error handler for 500 Internal Server Error
@app.errorhandler(500)
def server_error(e):
    logger.error(f"Unhandled error: {e}")
    return render_template("500.html"), 500


def load_printer_setting():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            return data.get("printer")
    return None


def save_printer_setting(printer_name):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"printer": printer_name}, f)


## Duplicate/errant settings() removed. Only the correct printer_settings() route remains above.


@app.route("/", methods=["GET"])
def index():
    logger.info("Rendering index page")
    return render_template("index.html")


@app.route("/print", methods=["POST"])
def print_url():
    url = request.form.get("url", "").strip()
    desc = request.form.get("description", "").strip()
    logger.info(f"Received print request: url={url}, desc={desc}")
    if not url or not desc:
        flash("Both URL and description are required.")
        logger.warning("Missing URL or description.")
        return redirect("/")
    if not is_valid_url(url):
        flash(
            "Invalid URL provided. Please enter a valid URL starting with http:// or https://"
        )
        logger.warning(f"Invalid URL: {url}")
        return redirect("/")
    try:
        qr_img = generate_qr_code(url)
    except Exception as e:
        logger.error(f"QR code generation failed: {e}\n{traceback.format_exc()}")
        flash("Failed to generate QR code. Please try again.")
        return redirect("/")
    try:
        pdf_bytes = create_pdf(qr_img, desc)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}\n{traceback.format_exc()}")
        flash("Failed to generate PDF. Please try again.")
        return redirect("/")
    try:
        send_to_printer(pdf_bytes)
    except cups.IPPError as e:
        logger.error(
            f"Printer unreachable or CUPS error: {e}\n{traceback.format_exc()}"
        )
        flash(
            "Printer unreachable or CUPS error. Please check your printer connection."
        )
        return redirect("/")
    except Exception as e:
        logger.error(f"Print job failed: {e}\n{traceback.format_exc()}")
        flash(f"Failed to send PDF to printer. Error: {e}. Please try again.")
        return redirect("/")
    logger.info("Print job completed successfully.")
    return render_template("result.html", status="Printed successfully!")


@app.route("/settings", methods=["GET", "POST"])
def printer_settings():
    message = None
    printers = []
    selected_printer = None
    try:
        conn = cups.Connection()
        printers = list(conn.getPrinters().keys())
        if printers:
            selected_printer = load_printer_setting() or printers[0]
        else:
            message = "No printers found. Please check your CUPS setup."
    except Exception as e:
        message = f"CUPS connection error: {e}"
    if request.method == "POST":
        chosen = request.form.get("printer")
        manual_printer = request.form.get("manual_printer", "").strip()
        if manual_printer:
            # Save manual printer URI directly
            save_printer_setting(manual_printer)
            selected_printer = manual_printer
            message = f"Manual printer '{manual_printer}' saved as default."
            # Optionally, add to printers list for display
            if manual_printer not in printers:
                printers.append(manual_printer)
        elif chosen in printers:
            save_printer_setting(chosen)
            selected_printer = chosen
            message = f"Printer '{chosen}' saved as default."
        else:
            message = "Invalid printer selection."
    return render_template(
        "settings.html",
        printers=printers,
        selected_printer=selected_printer,
        message=message,
    )


def is_valid_url(url: str) -> bool:
    from urllib.parse import urlparse

    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def generate_qr_code(data: str) -> Image.Image:
    logger.info(f"Generating QR code for: {data}")
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


def create_pdf(qr_img: Image.Image, description: str) -> bytes:
    logger.info("Generating PDF with QR code and description.")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(200 * mm, 250 * mm))
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), 50, 400, width=100, height=100)
    c.setFont("Helvetica", 12)
    c.drawCentredString(100, 380, description)
    c.showPage()
    c.save()
    return buf.getvalue()


def send_to_printer(pdf_bytes: bytes) -> None:
    import getpass
    import os
    import time

    logger.info("Sending PDF to printer.")
    try:
        user = getpass.getuser()
    except Exception:
        user = str(os.geteuid())
    logger.info(f"App running as user: {user} (uid={os.geteuid()})")
    import subprocess

    # Determine printer name
    printer = load_printer_setting() or os.getenv("PRINTER_NAME")
    if not printer:
        printer = "autoprinter"
    logger.info(f"Using printer: {printer}")
    pdf_path = "/tmp/qr_print.pdf"
    try:
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
            f.flush()
            os.fsync(f.fileno())
        logger.info(f"PDF written to {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to write PDF: {e}\n{traceback.format_exc()}")
        raise
    # Log file permissions
    try:
        stat = os.stat(pdf_path)
        logger.info(
            f"PDF file permissions: {oct(stat.st_mode)} owner: {stat.st_uid}:{stat.st_gid}"
        )
    except Exception as e:
        logger.warning(f"Could not stat PDF file: {e}")
    # Optional: short delay to ensure file is ready
    time.sleep(0.2)
    # Build lp command
    lp_cmd = ["lp"]
    if printer:
        lp_cmd += ["-d", printer]
    lp_cmd.append(pdf_path)
    logger.info(f"Running print command: {' '.join(lp_cmd)}")
    try:
        result = subprocess.run(lp_cmd, capture_output=True, text=True, check=True)
        logger.info(f"lp stdout: {result.stdout.strip()}")
        logger.info(f"lp stderr: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"lp command failed: {e}\nstdout: {e.stdout}\nstderr: {e.stderr}")
        raise RuntimeError(f"lp command failed: {e.stderr}")

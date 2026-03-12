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
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                return data.get("printer")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    return None


def save_printer_setting(printer_name):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"printer": printer_name}, f)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")


def register_printer(uri, name="manualprinter"):
    import subprocess
    logger.info(f"Attempting to register printer: {name} with URI: {uri}")
    try:
        # Use everywhere driver for IPP/AirPrint compatibility
        cmd = ["sudo", "lpadmin", "-p", name, "-E", "-v", uri, "-m", "everywhere"]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        # Verify it was added
        subprocess.run(["lpstat", "-p", name], check=True, capture_output=True)
        logger.info(f"Successfully registered printer {name}")
        return name
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to register printer {name}: {e.stderr}")
        # Try without -m everywhere as fallback
        try:
            logger.info("Retrying registration without '-m everywhere'...")
            cmd = ["sudo", "lpadmin", "-p", name, "-E", "-v", uri]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return name
        except Exception as e2:
            logger.error(f"Fallback registration also failed: {e2}")
            raise RuntimeError(f"Could not register printer URI: {e.stderr}")


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
        selected_printer = load_printer_setting()
        if not selected_printer and printers:
            selected_printer = printers[0]
    except Exception as e:
        logger.error(f"CUPS connection error: {e}")
        message = f"CUPS connection error: {e}"
        
    if request.method == "POST":
        chosen = request.form.get("printer")
        manual_printer = request.form.get("manual_printer", "").strip()
        
        if manual_printer:
            if "://" in manual_printer:
                try:
                    # If it looks like a URI, register it
                    name = register_printer(manual_printer)
                    save_printer_setting(name)
                    selected_printer = name
                    message = f"Printer URI registered as '{name}' and saved as default."
                    # Refresh printers list
                    try:
                        conn = cups.Connection()
                        printers = list(conn.getPrinters().keys())
                    except: pass
                except Exception as e:
                    message = f"Error: {e}"
            else:
                save_printer_setting(manual_printer)
                selected_printer = manual_printer
                message = f"Printer '{manual_printer}' saved as default."
        elif chosen:
            save_printer_setting(chosen)
            selected_printer = chosen
            message = f"Printer '{chosen}' saved as default."
            
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
    
    # Safeguard: if the printer setting is a URI, register it now
    if "://" in printer:
        logger.info(f"Printer setting looks like a URI, attempting registration: {printer}")
        try:
            printer = register_printer(printer)
        except Exception as e:
            logger.error(f"Failed to register URI {printer}: {e}")
            # We continue anyway, but it will likely fail below

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

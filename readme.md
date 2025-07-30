Here’s a comprehensive set of requirements you can drop into CoPilot (or any IDE) to scaffold your containerized QR‑printing web app:

---

## 1. Overview

A simple web service where a user pastes:

1. **URL**
2. **Description**

On submit, the app:

* Generates a QR code for the URL
* Renders a one‑page PDF with the QR code at top, description below
* Sends the PDF to your local printer via CUPS/IPP

Packaged as a Docker container for easy self‑hosting.

---

## 2. Functional Requirements

* **GET /**

  * Show HTML form with two fields:

    * `url`: text input, required, validates as URL
    * `description`: text input, required, max‑length 200
  * “Print” button to submit via POST

* **POST /print**

  * Validate inputs
  * Generate QR code image
  * Create printable PDF
  * Send PDF to printer
  * Return success/failure page

* **Error Handling**

  * Show user‐friendly messages if URL invalid, QR gen fails, PDF gen fails, or printer unreachable.

---

## 3. Technical Stack

* **Language & Framework**: Python 3.x + Flask
* **QR Code**: `qrcode` + `Pillow`
* **PDF Generation**: `reportlab` (or `fpdf2`)
* **Printing**: `pycups` (or shell `lpr` to `$PRINTER_URI`)
* **Containerization**: Docker (+ optional Docker Compose)
* **Web UI**: Jinja2 templates + minimal CSS (e.g. Bootstrap CDN)
* **Logging**: Python `logging` to stdout

---

## 4. Architecture & File Layout

```
/app
  ├─ app.py              # Flask app
  ├─ requirements.txt    # pinned deps
  ├─ Dockerfile
  ├─ templates/
  │    ├─ index.html
  │    └─ result.html
  └─ static/
       └─ style.css      # optional
```

---

## 5. Environment & Configuration

* **ENV VARS**

  * `PRINTER_URI` → e.g. `ipp://printer.local:631/ipp/print`
  * `FLASK_ENV` → `production` or `development`
  * `HOST` → default `0.0.0.0`
  * `PORT` → default `5000`

* **Volumes / Sockets**

  * Mount host CUPS socket:

    ```yaml
    volumes:
      - /var/run/cups/cups.sock:/var/run/cups/cups.sock
    ```
  * Or configure IPP printer via `PRINTER_URI`

---

## 6. Pseudocode & Core Functions

```python
# app.py
from flask import Flask, render_template, request, flash, redirect
import qrcode
from reportlab.pdfgen import canvas
import cups  # or subprocess to lpr
import io
import logging

app = Flask(__name__)
app.secret_key = 'CHANGE_ME'
logger = logging.getLogger(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/print', methods=['POST'])
def print_url():
    url = request.form.get('url', '').strip()
    desc = request.form.get('description', '').strip()
    if not is_valid_url(url):
        flash('Invalid URL provided.')
        return redirect('/')
    try:
        qr_img = generate_qr_code(url)
        pdf_bytes = create_pdf(qr_img, desc)
        send_to_printer(pdf_bytes)
        return render_template('result.html', status='Printed successfully!')
    except Exception as e:
        logger.exception("Print job failed")
        flash(f'Error: {e}')
        return redirect('/')

def is_valid_url(url: str) -> bool:
    # simple regex or urllib.parse check
    pass

def generate_qr_code(data: str) -> PIL.Image:
    """Return a QR code PIL Image for the given data."""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    return img

def create_pdf(qr_img: PIL.Image, description: str) -> bytes:
    """Render a one‐page PDF with the QR at top, text below."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(200*mm, 250*mm))
    # Draw QR image at (x, y)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format='PNG')
    c.drawImage(qr_buf, 50, 150, width=100, height=100)
    # Draw description text
    c.setFont("Helvetica", 12)
    c.drawCentredString(100, 130, description)
    c.showPage()
    c.save()
    return buf.getvalue()

def send_to_printer(pdf_bytes: bytes) -> None:
    """Use CUPS or lpr to send the PDF to the configured printer."""
    conn = cups.Connection()  # requires cups-devel in container
    printers = conn.getPrinters()
    uri = os.getenv('PRINTER_URI') or list(printers.keys())[0]
    job_id = conn.printJob(printer=uri, title="QR Print", filename=None, data=pdf_bytes)
    # or: subprocess.run(['lpr', '-P', uri], input=pdf_bytes)
    return
```

---

## 7. Dockerfile (outline)

```dockerfile
FROM python:3.11-slim

# system deps for CUPS and fonts
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libcups2-dev \
      fonts-dejavu-core \
      && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
ENV FLASK_APP=app.py
EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
```

---

## 8. (Optional) docker‑compose.yml

```yaml
version: '3.8'
services:
  qr-printer:
    build: .
    ports:
      - "5000:5000"
    environment:
      - PRINTER_URI=ipp://printer.local:631/ipp/print
      - FLASK_ENV=production
    volumes:
      - /var/run/cups/cups.sock:/var/run/cups/cups.sock
```

---

## 9. Deployment & Usage

1. **Build**

   ```bash
   docker build -t qr-print-app .
   ```
2. **Run**

   ```bash
   docker run -d \
     --name qr-print-app \
     -p 5000:5000 \
     -v /var/run/cups/cups.sock:/var/run/cups/cups.sock \
     -e PRINTER_URI=ipp://printer.local:631/ipp/print \
     qr-print-app
   ```
3. **Access**
   Navigate to `http://<host>:5000/`, paste your URL & description, hit Print.

---

With this spec in place, CoPilot should be able to scaffold your Flask app, PDF/QR code logic, and Docker setup in VS Code in one go. Let me know if you’d like more detail on any section!

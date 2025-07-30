FROM python:3.11-slim


# Install system dependencies and CUPS
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc \
      python3-dev \
      libcups2-dev \
      cups \
      cups-client \
      cups-bsd \
      fonts-dejavu-core \
      sudo \
      && rm -rf /var/lib/apt/lists/*

# Create app user, add to lp group for CUPS access
RUN useradd -m appuser && usermod -aG lp appuser && usermod -aG lpadmin appuser && echo 'appuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Expose CUPS web interface and listen on all interfaces
RUN sed -i 's/Listen localhost:631/Port 631\nListen 0.0.0.0:631/' /etc/cups/cupsd.conf && \
    sed -i 's/WebInterface No/WebInterface Yes/' /etc/cups/cupsd.conf

# Copy printer config if you want to pre-seed printers (optional)
# COPY printers.conf /etc/cups/printers.conf

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip --no-warn-script-location --no-cache-dir \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ruff


COPY . /app
RUN chown -R appuser:appuser /app
ENV FLASK_APP=app.py
EXPOSE 5000 631

# Start CUPS, auto-add printer if PRINTER_URI is set, then start Flask app as appuser
CMD ["sh", "-c", "service cups start && if [ -n \"$PRINTER_URI\" ]; then lpadmin -p autoprinter -E -v \"$PRINTER_URI\" -m everywhere; fi && if lpstat -p autoprinter > /dev/null 2>&1; then lpoptions -d autoprinter; fi && sudo -u appuser flask run --host=0.0.0.0 --port=5000"]

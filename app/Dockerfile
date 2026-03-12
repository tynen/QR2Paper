FROM python:3.13-bookworm


# Install system dependencies, CUPS, and mDNS support
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
      libnss-mdns \
      avahi-daemon \
      avahi-utils \
      && rm -rf /var/lib/apt/lists/*

# Create app user, add to lp group for CUPS access
RUN useradd -m appuser && usermod -aG lp appuser && usermod -aG lpadmin appuser && echo 'appuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Expose CUPS web interface and listen on all interfaces
RUN sed -i 's/Listen localhost:631/Port 631\nListen 0.0.0.0:631/' /etc/cups/cupsd.conf && \
    sed -i 's/WebInterface No/WebInterface Yes/' /etc/cups/cupsd.conf && \
    echo "DefaultEncryption Never" >> /etc/cups/cupsd.conf && \
    sed -i 's/<Location \/>/<Location \/>\n  Allow All/' /etc/cups/cupsd.conf && \
    sed -i 's/<Location \/admin>/<Location \/admin>\n  Allow All/' /etc/cups/cupsd.conf && \
    sed -i 's/<Location \/admin\/conf>/<Location \/admin\/conf>\n  Allow All/' /etc/cups/cupsd.conf

# Configure Avahi for container use (disable dbus requirement if possible, or just start it)
RUN sed -i 's/#enable-dbus=yes/enable-dbus=no/' /etc/avahi/avahi-daemon.conf

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip --no-warn-script-location --no-cache-dir \
    && pip install --no-cache-dir -r requirements.txt


COPY . /app
RUN chown -R appuser:appuser /app
ENV FLASK_APP=app.py
EXPOSE 5000 631

# Start services and then start Flask app
CMD ["sh", "-c", "service cups start && service avahi-daemon start && sleep 2 && if [ -n \"$PRINTER_URI\" ]; then lpadmin -p autoprinter -E -v \"$PRINTER_URI\" -m everywhere || lpadmin -p autoprinter -E -v \"$PRINTER_URI\"; fi && if lpstat -p autoprinter > /dev/null 2>&1; then lpoptions -d autoprinter; fi && sudo -u appuser flask run --host=0.0.0.0 --port=5000"]

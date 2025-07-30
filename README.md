# QR2Paper

QR2Paper is a web application that generates a printable PDF containing a QR code and description for any URL you provide. It is designed for easy deployment in environments with networked printers (CUPS/IPP) and is ideal for offices, schools, or anywhere you want to share digital resources on paper.

## Features
- Web UI for entering a URL and description
- Generates a PDF with a QR code and your description
- Sends the PDF directly to a network printer via CUPS
- Dockerized for easy deployment
- Supports printer selection and configuration

## Quick Start (Docker Compose)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tynen/QR2Paper.git
   cd QR2Paper
   ```
2. **Edit `compose.yaml`** to set your printer URI (IPP/CUPS):
   ```yaml
   environment:
     - PRINTER_URI=ipp://your-printer-uri/ipp/print
   ```
3. **Build and run:**
   ```bash
   ./fresh_build.sh
   # or
   docker compose up --build
   ```
4. **Access the app:**
   Open [http://localhost:5000](http://localhost:5000) in your browser.

## Deploy with Docker Hub
You can also pull the latest image from Docker Hub:
```bash
docker pull tynen/qr2paper:latest
docker run -d -e PRINTER_URI=ipp://your-printer-uri/ipp/print -p 5000:5000 tynen/qr2paper:latest
```

## Contributing
Contributions are welcome! To contribute:
1. Fork this repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Open a pull request

All pull requests are tested with CI and require code owner review.

## License
MIT License. See [LICENSE](LICENSE) for details.
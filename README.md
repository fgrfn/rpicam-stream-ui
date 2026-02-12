# 🎥 rpicam-stream-ui

Web-Interface zur Steuerung des Raspberry Pi Kamera RTSP Streams mit System-Monitoring.

## Features

- 📡 **RTSP Stream Control** - Start/Stop/Restart direkt aus dem Browser
- 🎛️ **Live-Konfiguration** - Alle rpicam-vid Parameter in Echtzeit anpassen
- 📊 **System-Monitoring** - CPU (Total + alle Kerne), RAM, Temperatur
- 🔄 **Pi Neustart** - Remote Reboot über Webinterface
- 🌐 **Auto LAN-IP** - Automatische Erkennung der aktuellen IP-Adresse
- 💾 **Config-Speicherung** - Einstellungen werden persistent gespeichert

## Voraussetzungen

- Raspberry Pi mit Kamera (CSI)
- Raspberry Pi OS (Debian Bookworm/Trixie)
- Python 3
- rpicam-vid (vorinstalliert auf Raspberry Pi)
- ffmpeg
- RTSP Server (z.B. mediamtx)

## Installation

### 1. Repository klonen

```bash
cd ~
git clone https://github.com/fgrfn/rpicam-stream-ui.git
cd rpicam-stream-ui
```

### 2. RTSP Server installieren (mediamtx)

```bash
# Mediamtx herunterladen
wget https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_arm64v8.tar.gz

# Entpacken
sudo mkdir -p /opt/mediamtx
sudo tar -xzf mediamtx_v1.6.0_linux_arm64v8.tar.gz -C /opt/mediamtx/
sudo chmod +x /opt/mediamtx/mediamtx

# Als Service einrichten
sudo tee /etc/systemd/system/mediamtx.service > /dev/null << 'EOF'
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/mediamtx/mediamtx /opt/mediamtx/mediamtx.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

### 3. Python Abhängigkeiten installieren

```bash
pip3 install flask
```

Oder systemweit:
```bash
sudo apt install -y python3-flask
```

### 4. Kamera Stream Service einrichten

```bash
# Service Datei erstellen
sudo tee /etc/systemd/system/pi_camera_stream.service > /dev/null << 'EOF'
[Unit]
Description=Pi Camera RTSP Stream
After=network.target mediamtx.service
Wants=mediamtx.service

[Service]
Type=simple
User=root
ExecStartPre=/bin/sleep 5
ExecStart=/bin/bash -c 'nice -n -11 rpicam-vid -b 6000000 --denoise auto --codec libav --libav-format mpegts --profile high --hdr off --level 4.1 --framerate 30 --width 1920 --height 1080 --intra 15 --av-sync 0 --awb indoor -t 0 --inline -n -o - | ffmpeg -hide_banner -fflags nobuffer -flags low_delay -probesize 64 -analyzeduration 0 -i - -map 0:v:0 -c copy -muxdelay 0 -muxpreload 0 -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/kali1080'
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pi_camera_stream
```

### 5. Web Interface Service einrichten

```bash
# Pfad anpassen falls nötig
WORKING_DIR="/home/pi/rpicam-stream-ui"  # oder /home/florian/rpicam-stream-ui

sudo tee /etc/systemd/system/pi_stream_control.service > /dev/null << EOF
[Unit]
Description=Pi Stream Control Web Interface
After=network.target pi_camera_stream.service

[Service]
Type=simple
User=root
WorkingDirectory=$WORKING_DIR
Environment=FLASK_APP=app.py
Environment=FLASK_ENV=production
ExecStart=/usr/bin/python3 $WORKING_DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pi_stream_control
```

### 6. nginx als Reverse Proxy (optional)

Für Port 80 statt 8080:

```bash
sudo apt install -y nginx

sudo tee /etc/nginx/sites-available/pi_stream_control > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/pi_stream_control /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Services starten

```bash
sudo systemctl start mediamtx
sudo systemctl start pi_camera_stream
sudo systemctl start pi_stream_control
```

## Verwendung

### Web Interface

Öffne im Browser:
- Mit nginx: `http://<raspberry-pi-ip>/`
- Ohne nginx: `http://<raspberry-pi-ip>:8080/`

### RTSP Stream URL

```
rtsp://<raspberry-pi-ip>:8554/kali1080
```

Diese URL kann in VLC, OBS oder andere RTSP-fähige Player verwendet werden.

### Features im Interface

- **Stream Status** - Zeigt ob der Stream läuft
- **CPU/RAM/Temp** - Echtzeit-Monitoring
- **CPU Kerne** - Individuelle Auslastung jedes Kerns
- **RTSP URL** - Kopierbar mit einem Klick
- **Konfiguration** - Alle Kamera-Parameter anpassbar
- **Pi Neustart** - Remote Reboot des Raspberry Pi

## Konfiguration

Die Einstellungen werden in `stream_config.json` gespeichert:

```json
{
  "bitrate": 6000000,
  "denoise": "auto",
  "codec": "libav",
  "libav_format": "mpegts",
  "profile": "high",
  "hdr": "off",
  "level": "4.1",
  "framerate": 30,
  "width": 1920,
  "height": 1080,
  "intra": 15,
  "av_sync": 0,
  "awb": "indoor",
  "rtsp_host": "",
  "rtsp_port": 8554,
  "rtsp_path": "kali1080",
  "nice": -11
}
```

### Parameter Erklärung

| Parameter | Beschreibung | Standard |
|-----------|--------------|----------|
| `bitrate` | Video-Bitrate in bps | 6000000 |
| `framerate` | FPS | 30 |
| `width/height` | Auflösung | 1920x1080 |
| `awb` | Weißabgleich (auto/indoor/outdoor) | indoor |
| `denoise` | Rauschunterdrückung | auto |
| `hdr` | High Dynamic Range | off |
| `intra` | Keyframe-Intervall | 15 |
| `nice` | Prozess-Priorität | -11 |

## API Endpunkte

- `GET /api/config` - Konfiguration laden
- `POST /api/config` - Konfiguration speichern
- `POST /api/stream/start` - Stream starten
- `POST /api/stream/stop` - Stream stoppen
- `POST /api/stream/restart` - Stream neustarten
- `GET /api/stream/status` - Stream Status
- `GET /api/system/stats` - System-Stats (CPU, RAM, Temp)
- `POST /api/system/reboot` - Pi neustarten

## Fehlersuche

### Stream startet nicht

```bash
# Logs prüfen
sudo journalctl -u pi_camera_stream -f

# Manuelles Testen
sudo rpicam-vid -b 6000000 --denoise auto --codec libav --framerate 30 --width 1920 --height 1080 -t 0 -o - | ffmpeg -i - -f rtsp rtsp://127.0.0.1:8554/test
```

### Web Interface nicht erreichbar

```bash
# Status prüfen
sudo systemctl status pi_stream_control

# Port prüfen
sudo ss -tlnp | grep 8080

# Logs ansehen
sudo journalctl -u pi_stream_control -f
```

### RTSP Server prüfen

```bash
# mediamtx läuft?
sudo systemctl status mediamtx

# Port 8554 offen?
sudo ss -tlnp | grep 8554
```

## Lizenz

MIT License - Siehe [LICENSE](LICENSE)

## Autor

- **nookie** - GitHub: [@fgrfn](https://github.com/fgrfn)

---

🦞 Powered by OpenClaw

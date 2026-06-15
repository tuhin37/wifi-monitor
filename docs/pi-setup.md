# Raspberry Pi Setup

## Hardware

- Raspberry Pi 4 (2GB+) or Pi 5
- 32GB+ microSD (Class 10/A2)
- **USB Wi-Fi adapter** for monitoring (built-in Wi-Fi does NOT support monitor mode)
- Ethernet or a second USB Wi-Fi dongle for management

## Steps

```bash
# Flash Raspberry Pi OS Lite (64-bit)

# Install deps
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git iw ethtool

# Clone repo
git clone https://github.com/tuhin37/wifi-monitor.git
cd wifi-monitor

# Put USB adapter in monitor mode
sudo ./scripts/setup-monitor-mode.sh wlan1

# Configure
cp .env.example .env
# Edit .env: set SCANNER_INTERFACE=wlan1, MGMT_INTERFACE=wlan0 (or eth0)

# Deploy
docker compose up -d

# Grafana at http://<pi-ip>:3000
```

## Multi-Node

Deploy one Pi per location, then configure a central Grafana instance that scrapes each Pi's Prometheus.

| Pi Model | Devices | RAM |
|----------|---------|-----|
| Pi 4 (2GB) | ~500 | ~500MB |
| Pi 4 (4GB) | ~1000 | ~800MB |
| Pi 5 (4GB+) | 2000+ | ~1.2GB |

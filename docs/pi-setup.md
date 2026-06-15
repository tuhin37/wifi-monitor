# Raspberry Pi Setup Guide

This guide walks through deploying the WiFi Monitor stack on a Raspberry Pi for distributed Wi-Fi surveying — place Pi + USB Wi-Fi adapter combos around your home/office to monitor channel utilization and AP coverage from multiple vantage points.

## Recommended Hardware

| Component | Recommendation | Why |
|-----------|---------------|-----|
| **Pi Board** | Raspberry Pi 4 (2GB+) or Pi 5 | Enough RAM for Kismet + Docker |
| **Storage** | 32GB+ microSD (Class 10/A2) or USB SSD | SQLite DB grows over time |
| **Wi-Fi Adapter** | Alfa AWUS036ACHM (RTL8812AU) or AWUS036ACH (AR9271) | Proven monitor-mode support |
| **Power** | Official Pi PSU or 3A+ USB-C | USB adapters draw additional power |
| **Case** | Any vented case | USB adapter can get warm |
| **Network** | Ethernet or secondary USB Wi-Fi dongle | Monitor-mode adapter can't do normal networking |

> **Important**: The Raspberry Pi's built-in Broadcom Wi-Fi (brcmfmac) does NOT support monitor mode. You MUST use a separate USB Wi-Fi adapter.

## Step 1: Prepare the Pi

### Flash Raspberry Pi OS Lite (64-bit)

```bash
# Download
wget https://downloads.raspberrypi.com/raspios_lite_arm64_latest

# Flash to SD card (replace /dev/sdX)
sudo dd if=raspios-lite-arm64.img of=/dev/sdX bs=4M status=progress
```

### Enable SSH and pre-configure Wi-Fi

Create an empty `ssh` file and a `userconf.txt` on the boot partition, then:

```bash
# On the boot partition, create userconf.txt with:
echo '<username>:<encrypted-password>' > /boot/firmware/userconf.txt

# Create wpa_supplicant.conf for initial network access:
# (if using a secondary USB adapter for management)
```

Or just plug in a keyboard + monitor for initial setup.

### System Setup

```bash
# Update and install prerequisites
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git iw ethtool aircrack-ng

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin (if not already present)
sudo apt install -y docker-compose-v2

# Clone the repo
git clone https://github.com/tuhin37/wifi-monitor.git
cd wifi-monitor
```

## Step 2: Setup Wi-Fi Adapter

### For Alfa AWUS036ACHM (RTL8812AU)

```bash
# Install the driver
sudo apt install -y dkms
git clone https://github.com/morrownr/8821au-20210708.git
cd 8821au-20210708
sudo ./install-driver.sh

# Reboot
sudo reboot
```

### For Alfa AWUS036ACH (AR9271)

```bash
# AR9271 works out of the box with the in-kernel ath9k_htc driver
sudo modprobe ath9k_htc
```

### Put the adapter in monitor mode

```bash
# Identify your USB adapter interface
iw dev
# Usually wlan1 if built-in Wi-Fi is wlan0

# Run the setup script
sudo ./scripts/setup-monitor-mode.sh wlan1
```

**Important**: If you want the Pi to also connect to your network (to reach Grafana), you need TWO Wi-Fi interfaces: one for monitoring (e.g., Alfa on wlan1) and one for management connectivity (built-in on wlan0, or a second USB adapter).

Alternatively, use Ethernet for management and dedicate the USB adapter solely to monitoring.

## Step 3: Deploy the Stack

```bash
# Create .env from example
cp .env.example .env

# Edit .env to set your WIFI_INTERFACE
nano .env

# Start the stack
docker compose up -d

# Check logs
docker compose logs -f exporter
docker compose logs -f kismet
```

## Step 4: Access the Dashboard

Find the Pi's IP address:

```bash
hostname -I
```

Then open `http://<pi-ip>:3000` in your browser. Login with `admin` / `admin` (or whatever you set in `.env`).

The dashboard should auto-provision — look for "WiFi Monitor" under Dashboards.

## Multi-Node Deployment (Whole-Home Coverage)

To monitor Wi-Fi from multiple physical locations (e.g., living room, bedroom, garage):

1. Set up a Pi + USB adapter at each location
2. Run `docker compose up -d` on each Pi
3. Either:
   - **Separate Grafana per Pi** — access each at its own IP:3000
   - **Central Grafana** — configure each Pi's Prometheus as a separate data source in a single Grafana instance, then use dashboard variables to switch between nodes

### Central Grafana Setup

On your central server, add each Pi's Prometheus as a data source:

```yaml
# Additional datasources in grafana/datasources/
apiVersion: 1
datasources:
  - name: Prometheus-LivingRoom
    type: prometheus
    url: http://192.168.1.10:9090
  - name: Prometheus-Bedroom
    type: prometheus
    url: http://192.168.1.11:9090
```

Then use the dashboard's variable system to switch between nodes.

## Performance Notes

| Pi Model | Devices Tracked | RAM Usage | Notes |
|----------|----------------|-----------|-------|
| Pi 4 (2GB) | ~500 | ~500MB | Fine for home use |
| Pi 4 (4GB) | ~1000 | ~800MB | Recommended |
| Pi 5 (4GB) | ~2000 | ~1.2GB | Excellent |
| Pi 5 (8GB) | Unlimited | ~1.5GB+ | Heavy use |

## Troubleshooting

**"No devices detected"** — Kismet may not be seeing packets. Check:
```bash
sudo iw dev wlan1 info  # Should show 'type monitor'
sudo tcpdump -i wlan1 -c 10  # Should show packets
```

**"Kismet container exits immediately"** — Usually a monitor-mode issue:
```bash
docker compose logs kismet
```

**High CPU usage** — Reduce `POLL_INTERVAL` in `.env` or limit device tracking in `kismet_site.conf`:
```
max_devices=500
tracker_device_timeout=1800
```

**"exporter: connection refused"** — Kismet takes time to start. Wait 30s or check:
```bash
curl http://127.0.0.1:2501/session/check
```

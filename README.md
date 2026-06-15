# Wi-Fi Monitor

Self-hosted, Docker Compose-based Wi-Fi spectrum and AP monitoring stack. Track access points, channels, RSSI, signal quality, band distribution, and channel utilization from any Linux host (including Raspberry Pi) with a monitor-mode wireless NIC.

```
┌──────────────┐    ┌─────────────────┐    ┌────────────┐    ┌─────────┐
│ Wi-Fi Adapter │───▶│    Kismet       │───▶│  Exporter  │───▶│ Grafana │
│ (Monitor Mode)│    │ (802.11 sniffer)│    │(Prometheus)│    │(Dashboard)│
└──────────────┘    └─────────────────┘    └─────┬──────┘    └─────────┘
                                                  │
                                                  ▼
                                           ┌────────────┐
                                           │ Prometheus  │
                                           │  (TSDB)     │
                                           └────────────┘
```

## Features

- **AP Discovery** — Automatically detects all Wi-Fi access points and clients in range
- **Signal Strength** — Real-time RSSI tracking per device with configurable thresholds
- **Channel Analysis** — See which channels are in use and how many APs occupy each
- **Band Distribution** — 2.4 GHz vs 5 GHz vs 6 GHz breakdown
- **Signal-to-Noise Ratio** — SNR tracking for signal quality assessment
- **Channel Utilization** — Percentage of airtime used per channel (via `iw survey dump`)
- **Vendor Identification** — Manufacturer info for detected devices
- **Encryption Detection** — WEP, WPA, WPA2, WPA3 identification
- **Client Density** — APs with the most connected clients
- **Historical Trends** — All metrics stored in Prometheus for historical analysis
- **Multi-Node Ready** — Deploy on multiple Pis for whole-home coverage
- **Pre-built Dashboard** — 20+ panel Grafana dashboard auto-provisions

## Quick Start

### Prerequisites

- Linux host (Debian/Ubuntu/Raspberry Pi OS recommended)
- Docker + Docker Compose v2
- A compatible Wi-Fi adapter (see [docs/hardware.md](docs/hardware.md))

### One-Line Deploy

```bash
# Clone
git clone https://github.com/tuhin37/wifi-monitor.git
cd wifi-monitor

# Put adapter in monitor mode
sudo ./scripts/setup-monitor-mode.sh wlan1

# Configure
cp .env.example .env
# Edit .env to set WIFI_INTERFACE=wlan1

# Launch
docker compose up -d

# Open Grafana: http://<host-ip>:3000 (admin/admin)
```

> **Note**: The Grafana dashboard auto-provisions. Navigate to **Dashboards > WiFi Monitor** once the stack is running.

### For Raspberry Pi

See the dedicated guide: [docs/pi-setup.md](docs/pi-setup.md)

## Architecture

| Component | Role | Port |
|-----------|------|------|
| **Kismet** | 802.11 wireless sniffer and AP detector | 2501 (REST API) |
| **Exporter** | Custom Python Prometheus exporter — translates Kismet data into metrics | 8501 |
| **Prometheus** | Time-series database for metric storage | 9090 |
| **Grafana** | Visualization and dashboards | 3000 |

### Prometheus Metrics

The exporter provides the following metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `wifi_ap_info` | Info | Static metadata (MAC, SSID, channel, band, encryption, vendor) |
| `wifi_ap_signal_dbm` | Gauge | Current RSSI signal strength in dBm |
| `wifi_ap_snr_db` | Gauge | Signal-to-noise ratio in dB |
| `wifi_ap_frequency_mhz` | Gauge | Operating center frequency in MHz |
| `wifi_ap_channel_width_mhz` | Gauge | Channel width in MHz (where detectable) |
| `wifi_ap_uptime_seconds` | Gauge | BSS uptime in seconds |
| `wifi_ap_clients` | Gauge | Number of associated clients per AP |
| `wifi_ap_packets_total` | Counter | Total packets seen for device |
| `wifi_ap_data_bytes_total` | Counter | Total data volume per device |
| `wifi_channel_utilization_percent` | Gauge | Channel utilization % from iw survey dump |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KISMET_USERNAME` | `admin` | Kismet REST API username |
| `KISMET_PASSWORD` | `admin` | Kismet REST API password |
| `EXPORTER_PORT` | `8501` | Prometheus exporter HTTP port |
| `WIFI_INTERFACE` | (empty) | Wireless interface for iw survey (e.g. wlan1) |
| `POLL_INTERVAL` | `15` | Kismet polling interval in seconds |
| `PROMETHEUS_PORT` | `9090` | Prometheus web interface port |
| `PROMETHEUS_RETENTION` | `30d` | Prometheus data retention period |
| `GRAFANA_PORT` | `3000` | Grafana web interface port |
| `GRAFANA_USER` | `admin` | Grafana admin username |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |

### Dashboard Variables

The Grafana dashboard includes filter variables for:

- **Band** — Filter by 2.4 GHz / 5 GHz / 6 GHz
- **SSID** — Filter by specific network name

## Project Structure

```
wifi-monitor/
├── docker-compose.yml              # Full stack orchestration
├── .env.example                    # Environment config template
├── exporter/
│   ├── Dockerfile                  # Custom exporter container
│   ├── exporter.py                 # Prometheus metrics collection
│   ├── channel_map.py              # Frequency-to-channel mapping
│   └── requirements.txt            # Python dependencies
├── kismet/
│   └── kismet_site.conf            # Kismet configuration template
├── prometheus/
│   └── prometheus.yml              # Prometheus scrape configuration
├── grafana/
│   ├── datasources/
│   │   └── datasource.yml          # Auto-provisioned Prometheus datasource
│   └── dashboards/
│       ├── dashboard.yml           # Dashboard provisioning config
│       └── wifi-monitoring.json    # Pre-built WiFi monitoring dashboard
├── scripts/
│   ├── setup-monitor-mode.sh       # Enable monitor mode on a Wi-Fi interface
│   └── check-nic.sh                # Check adapter compatibility
└── docs/
    ├── hardware.md                 # Supported Wi-Fi adapters
    ├── pi-setup.md                 # Raspberry Pi deployment guide
    └── troubleshooting.md          # Common issues and solutions
```

## Hardware

You need a Wi-Fi adapter that supports **monitor mode**. Built-in laptop/Pi Wi-Fi usually won't work.

**Recommended adapters:**
- Alfa AWUS036ACHM (RTL8812AU) — dual-band USB, ~$50
- Alfa AWUS036ACH (AR9271) — 2.4 GHz USB, works out of box
- Intel AX210 — tri-band (2.4/5/6 GHz) M.2, ~$25

Full compatibility list: [docs/hardware.md](docs/hardware.md)

## Multi-Node Deployments

Place Raspberry Pi + USB adapter combos at different physical locations for whole-home coverage:

```
Living Room Pi ──▶ Prometheus ──┐
Bedroom Pi    ──▶ Prometheus ──┤──▶ Grafana (central)
Garage Pi     ──▶ Prometheus ──┘
```

See [docs/pi-setup.md](docs/pi-setup.md) for multi-node instructions.

## Development

### Building the Exporter Locally

```bash
cd exporter
pip install -r requirements.txt

# Test (requires Kismet running)
KISMET_URL=http://localhost:2501 \
KISMET_USERNAME=admin \
KISMET_PASSWORD=admin \
python exporter.py
```

## License

MIT

## See Also

- [Kismet](https://www.kismetwireless.net/) — The wireless sniffer that powers this stack
- [Prometheus](https://prometheus.io/) — Time-series monitoring
- [Grafana](https://grafana.com/) — Dashboard visualization

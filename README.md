# Wi-Fi Monitor

A self-hosted Docker Compose stack that passively scans Wi-Fi APs and runs automated speed tests against them. All data is exposed as Prometheus metrics — visualize in Grafana.

```
┌──────────────┐    ┌──────────────────┐    ┌────────────┐    ┌─────────┐
│ Wi-Fi Adapter │───▶│   Kismet / iw    │───▶│  Exporter  │───▶│ Grafana │
│ (monitor mode)│    │  (passive scan)  │    │(Prometheus)│    │(Dashboard)│
└──────────────┘    └──────────────────┘    └─────┬──────┘    └─────────┘
                                                    │
              ┌─────────────────────────────────────┤
              │          ┌──────────────────────┐   │
              │          │  Task Scheduler      │   │
              │          │  (APScheduler)       │   │
              │          │                      │   │
              │          │  Connect to AP ──────┤   │
              │          │  Run speedtest ──────┤   │
              │          │  Record results      │   │
              │          └──────────────────────┘   │
              ▼                                     ▼
       ┌────────────┐                        ┌────────────┐
       │  Prometheus │◄──────────────────────┤  /metrics   │
       │   (TSDB)    │                       │   port 8501 │
       └────────────┘                        └────────────┘
```

## What It Does

- **Passive scanning** — Detects all Wi-Fi APs and clients in range via Kismet (or built-in `iw` scan)
- **Scheduled speed tests** — Connect to configured APs on a cron schedule, run download/upload speed tests, and record results
- **Prometheus metrics** — All data exposed at `/metrics` on port 8501
- **Grafana dashboard** — Pre-built dashboard auto-provisions on first deploy

## Quick Start

```bash
git clone https://github.com/tuhin37/wifi-monitor.git
cd wifi-monitor

# Put your Wi-Fi adapter in monitor mode (for scanning)
sudo ./scripts/setup-monitor-mode.sh wlan1

# Configure
cp .env.example .env
# Edit .env — set SCANNER_INTERFACE and MGMT_INTERFACE

# Start the stack
docker compose up -d

# Open Grafana at http://<host-ip>:3000 (admin/admin)
# Dashboard is at Dashboards > WiFi Monitor
```

## Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `wifi_ap_signal_dbm` | Gauge | RSSI per device, labels: bssid, ssid, type |
| `wifi_ap_snr_db` | Gauge | Signal-to-noise ratio |
| `wifi_ap_frequency_mhz` | Gauge | Center frequency |
| `wifi_ap_channel` | Gauge | Channel number |
| `wifi_ap_band` | Gauge | 1=2.4GHz, 2=5GHz, 3=6GHz |
| `wifi_ap_count` | Gauge | AP count by band |
| `wifi_speedtest_download_bps` | Gauge | Last download bitrate |
| `wifi_speedtest_upload_bps` | Gauge | Last upload bitrate |
| `wifi_speedtest_ping_ms` | Gauge | Last ping latency |
| `wifi_speedtest_jitter_ms` | Gauge | Last jitter |
| `wifi_speedtest_packet_loss` | Gauge | Last packet loss ratio |
| `wifi_speedtest_total` | Counter | Speedtest count by status |
| `wifi_scheduled_tasks_total` | Gauge | Active scheduled tasks |
| `wifi_scanner_up` | Gauge | Scanner health (1=up) |

## Scheduled Tasks (Speed Tests)

The stack includes a built-in task scheduler. You can add tasks via the API that:
1. Connect to a target AP using stored credentials
2. Run a speed test (download + upload)
3. Record results in SQLite and update Prometheus metrics
4. Disconnect

### Adding a task

```bash
# Via the HTTP API (once the stack is running)
curl -X POST http://localhost:8501/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Living Room AP",
    "ssid": "MyWiFi",
    "bssid": "aa:bb:cc:dd:ee:ff",
    "credentials": {"password": "secret123"},
    "schedule": "0 */6 * * *"
  }'
```

### Listing tasks

```bash
curl http://localhost:8501/api/tasks
```

## Requirements

- Linux host (Debian/Ubuntu/Raspberry Pi OS recommended)
- Docker + Docker Compose v2
- **Two Wi-Fi interfaces** recommended:
  - `wlan1` — monitor mode (Kismet passive scanning)
  - `wlan0` — managed mode (connecting to APs for speed tests)

### Hardware

See [docs/hardware.md](docs/hardware.md) for compatible Wi-Fi adapters.

## Config

Environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCANNER_INTERFACE` | wlan1 | Monitor-mode interface |
| `SCANNER_BACKEND` | kismet | "kismet" or "iw" |
| `MGMT_INTERFACE` | wlan0 | Interface for AP connections |
| `WIFI_BACKEND` | nmcli | "nmcli" or "wpa_supplicant" |
| `SPEEDTEST_BACKEND` | speedtest-cli | "speedtest-cli" or "iperf3" |
| `POLL_INTERVAL` | 15 | Scan interval (seconds) |

## Project Structure

```
wifi-monitor/
├── docker-compose.yml              # Full stack
├── .env.example                    # Environment config
├── config.yml                      # YAML config alternative
├── exporter/
│   ├── Dockerfile                  # Collector container
│   ├── main.py                     # Entry point
│   ├── config.py / database.py     # Config, SQLite storage
│   ├── scanner.py                  # Kismet / iw scanner
│   ├── wifi_connector.py           # nmcli / wpa_supplicant
│   ├── speedtest.py                # speedtest-cli / iperf3
│   ├── scheduler.py                # APScheduler tasks
│   └── metrics.py                  # Prometheus metrics
├── kismet/kismet_site.conf         # Kismet config
├── prometheus/prometheus.yml       # Prometheus config
├── grafana/
│   ├── datasources/datasource.yml  # Auto-provisioned
│   └── dashboards/wifi-monitoring.json  # Pre-built dashboard
├── scripts/
│   ├── setup-monitor-mode.sh       # Enable monitor mode
│   └── check-nic.sh                # Check compatibility
├── docs/
│   ├── hardware.md                 # Adapter compatibility
│   ├── pi-setup.md                 # Pi deployment
│   └── troubleshooting.md          # Common issues
└── README.md
```

## Architecture

The exporter runs three concurrent loops:
1. **Scanner loop** — polls Kismet REST API or runs `iw scan`, stores in SQLite, updates Prometheus metrics
2. **Scheduler** — runs APScheduler tasks on cron schedules, connects to APs and runs speed tests
3. **HTTP server** — exposes `/metrics` for Prometheus scraping and `/api/tasks` for task management

## License

MIT

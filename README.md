# WiFi Monitor

Exporter-only Wi-Fi monitoring stack for Prometheus and Grafana.

This repo contains:

- a Python Prometheus exporter that scans nearby Wi-Fi APs with `iw`
- Docker image build files for the exporter
- production Docker Compose for the beast homelab host
- a local development compose file for building/testing repo changes
- Grafana dashboard JSON for the WiFi Monitor dashboard

Current production image:

```text
fidays/wifi-monitor-exporter:latest
```

Current production topology:

```text
beast / 10.0.0.25
  wifimon-exporter
    image: fidays/wifi-monitor-exporter:latest
    host network + privileged
    metrics: http://10.0.0.25:8501/metrics
    data: /opt/stacks/wifi-mon/data -> /data

neutron / 10.0.0.47
  Prometheus scrape job: wifi-monitor -> 10.0.0.25:8501
  Grafana dashboard uid: wifi-monitor
```

## Architecture

```text
Wi-Fi NIC on beast
  -> iw scan inside privileged container
  -> SQLite cache under /data
  -> Prometheus exporter on :8501
  -> central Prometheus on neutron
  -> central Grafana on neutron
```

`compose.yaml` is the production stack file. It intentionally uses the Docker Hub image and does not build locally.

`docker-compose.dev.yml` is for development and local testing. It builds from `./exporter` and tags the local image as `wifi-monitor-exporter:local`.

## Production deploy on beast

Production runs from Docker Hub:

```bash
cd /opt/stacks/wifi-mon

docker compose -f compose.yaml pull exporter
docker compose -f compose.yaml up -d exporter
```

Verify:

```bash
docker ps --filter name=wifimon-exporter --format '{{.Names}} {{.Image}} {{.Status}}'
curl -fsS http://127.0.0.1:8501/metrics | grep -c '^wifi_ap_signal_dbm{'
```

Expected image:

```text
fidays/wifi-monitor-exporter:latest
```

## Automated release and production deploy

Merging a pull request into `main` triggers `.github/workflows/release-and-deploy.yml`.

The workflow runs on a self-hosted GitHub Actions runner and does the full production release:

1. Checks out the updated `main` branch.
2. Finds the latest semver Git tag matching `vX.Y.Z` and increments the patch version.
   - If no semver tag exists, the first release is `v0.0.1`.
3. Builds the exporter image from `exporter/Dockerfile.dev`.
4. Pushes both tags to Docker Hub:
   - `fidays/wifi-monitor-exporter:vX.Y.Z`
   - `fidays/wifi-monitor-exporter:latest`
5. Creates and pushes the matching Git tag.
6. SSHes to beast over NetBird (`100.77.113.19` by default).
7. Stops the WiFi exporter stack, updates `/opt/stacks/wifi-mon/compose.yaml` with the new immutable image tag, pulls it, restarts the stack, and verifies metrics.

Required GitHub Actions secrets:

```text
DOCKERHUB_USERNAME      Docker Hub username, normally fidays
DOCKERHUB_TOKEN         Docker Hub access token/password
BEAST_SSH_PASSWORD      SSH password for BEAST_SSH_USER
```

Optional secrets override the defaults:

```text
BEAST_HOST              default: 100.77.113.19
BEAST_SSH_USER          default: drag
BEAST_SSH_PORT          default: 22
BEAST_STACK_DIR         default: /opt/stacks/wifi-mon
```

Beast is username/password based. The workflow disables public-key auth for the deploy SSH command and uses `sshpass`. If `sshpass` is missing on the self-hosted runner, the workflow attempts to install it with `apt-get`/`sudo`; otherwise it fails with a clear message.

## Development workflow: change, build locally, test, promote

Use this when changing exporter code manually outside the automated release path.

### 1. Edit the repo

```bash
git clone git@github.com:tuhin37/wifi-monitor.git
cd wifi-monitor
```

Make code changes under `exporter/`.

Important files:

```text
exporter/main.py       HTTP server and scanner loop
exporter/scanner.py    iw scan parser
exporter/metrics.py    Prometheus metric definitions
exporter/database.py   SQLite persistence
exporter/config.py     environment config
```

### 2. Build the local image

```bash
docker compose -f docker-compose.dev.yml build exporter
```

This builds:

```text
wifi-monitor-exporter:local
```

Equivalent direct Docker command:

```bash
docker build -f exporter/Dockerfile.dev -t wifi-monitor-exporter:local exporter
```

### 3. Test locally

The dev compose file runs the locally-built exporter image plus a local Prometheus instance.

```bash
docker compose -f docker-compose.dev.yml up -d exporter prometheus
```

Verify the exporter:

```bash
docker ps --filter name=wifimon-exporter --format '{{.Names}} {{.Image}} {{.Status}}'
curl -fsS http://127.0.0.1:8501/metrics | grep -c '^wifi_ap_signal_dbm{'
curl -fsS http://127.0.0.1:8501/metrics | grep '^wifi_scanner_up'
```

Verify local Prometheus scrape:

```bash
curl -fsS http://127.0.0.1:9090/api/v1/targets \
  | python3 -m json.tool \
  | grep -A8 'wifi-monitor'
```

Notes:

- The exporter needs `network_mode: host` and `privileged: true` so `iw scan` can access the host Wi-Fi interface.
- Default interface is `wlp5s0`; change `SCANNER_INTERFACE` in the compose file if needed.
- The exporter stores SQLite data in `./data`, which is ignored by git.

### 4. Commit repo changes

```bash
git status
git add exporter docker-compose.dev.yml compose.yaml grafana README.md
git commit -m "<message>"
```

Only commit source/config/docs. Do not commit `data/`, SQLite files, or local `.env` files.

### 5. Promote a tested local image with an incremental tag

Manual promotion should use the same semver convention as the automated pipeline:

```text
vX.Y.Z
```

For normal patch releases, increment the last component, for example `v0.0.7` -> `v0.0.8`.

Find existing tags in Docker Hub:

```bash
docker pull fidays/wifi-monitor-exporter:latest
# or inspect in Docker Hub UI: https://hub.docker.com/r/fidays/wifi-monitor-exporter/tags
```

Set the next tag:

```bash
export TAG=v0.0.8
```

Tag the tested local image:

```bash
docker tag wifi-monitor-exporter:local fidays/wifi-monitor-exporter:${TAG}
docker tag wifi-monitor-exporter:local fidays/wifi-monitor-exporter:latest
```

Login to Docker Hub personal account if needed:

```bash
docker login -u fidays
```

Push both immutable/incremental and latest tags:

```bash
docker push fidays/wifi-monitor-exporter:${TAG}
docker push fidays/wifi-monitor-exporter:latest
```

Record the pushed digest:

```bash
docker image inspect fidays/wifi-monitor-exporter:${TAG} \
  --format '{{range .RepoDigests}}{{println .}}{{end}}'
```

### 6. Deploy the promoted image

Production currently tracks `latest`, so after pushing `latest`:

```bash
cd /opt/stacks/wifi-mon
docker compose -f compose.yaml pull exporter
docker compose -f compose.yaml up -d exporter
```

If you want production pinned to a specific incremental tag instead of `latest`, edit `compose.yaml`:

```yaml
image: fidays/wifi-monitor-exporter:v0.0.8
```

Then deploy:

```bash
docker compose -f compose.yaml pull exporter
docker compose -f compose.yaml up -d exporter
```

Commit the tag pin if you change it:

```bash
git add compose.yaml
git commit -m "Pin WiFi monitor exporter image to v2"
git push origin main
```

## Metrics

All metrics are Prometheus gauges unless noted.

| Metric | Labels | Description |
|---|---|---|
| `wifi_ap_signal_dbm` | `bssid`, `ssid`, `ssid_key`, `type`, `band`, `freq` | RSSI in dBm. `ssid_key` is URL-quoted for safe Grafana filtering. `band` is `2.4 GHz`, `5 GHz`, or `6 GHz`. `freq` is center frequency as a string label. |
| `wifi_ap_frequency_mhz` | `bssid`, `ssid` | Center frequency in MHz. |
| `wifi_ap_channel` | `bssid`, `ssid` | Wi-Fi channel number. |
| `wifi_ap_band` | `bssid`, `ssid` | Numeric band code: 1 = 2.4 GHz, 2 = 5 GHz, 3 = 6 GHz. |
| `wifi_ap_count` | `band` | AP count per band. |
| `wifi_scanner_up` | none | Scanner health: 1 = up, 0 = failed. |

Example scrape:

```bash
curl -fsS http://127.0.0.1:8501/metrics | grep '^wifi_ap_signal_dbm{' | head
```

## Grafana dashboard

Dashboard JSON:

```text
grafana/dashboards/wifi-monitoring.json
```

Production Grafana runs on neutron. Import dashboard changes into central Grafana; do not run a separate Grafana for production WiFi monitor.

Important dashboard conventions:

- Datasource is central Prometheus on neutron.
- Dashboard UID is `wifi-monitor`.
- SSID display uses original `ssid` values.
- PromQL filters use `ssid_key` so SSIDs with regex metacharacters like `+`, `.`, `(`, `)` work correctly.
- Signal-strength bar gauges use `sort_desc(...)` and instant queries (`instant: true`, `range: false`) so sorting is stable.

## Production compose

`compose.yaml`:

```yaml
name: wifi-mon
services:
  exporter:
    image: fidays/wifi-monitor-exporter:latest
    container_name: wifimon-exporter
    restart: unless-stopped
    network_mode: host
    privileged: true
    environment:
      EXPORTER_PORT: "8501"
      DATA_DIR: /data
      SCANNER_BACKEND: iw
      SCANNER_INTERFACE: wlp5s0
      POLL_INTERVAL: "15"
    volumes:
      - ./data:/data
```

## Troubleshooting

Check container:

```bash
docker ps --filter name=wifimon-exporter --format '{{.Names}} {{.Image}} {{.Status}}'
```

Check metrics:

```bash
curl -fsS http://127.0.0.1:8501/metrics | grep -E '^wifi_(scanner_up|ap_signal_dbm)'
```

Check Wi-Fi scan from inside the container:

```bash
docker exec wifimon-exporter iw dev wlp5s0 scan 2>&1 | grep -c '^BSS '
```

Check neutron Prometheus scrape:

```bash
curl -fsS http://10.0.0.47:9090/api/v1/targets \
  | python3 -m json.tool \
  | grep -A8 'wifi-monitor'
```

Common issue: interface down. Bring it up on the host or from the privileged container:

```bash
docker exec wifimon-exporter ip link set wlp5s0 up
```

## Repository hygiene

Ignored runtime data:

```text
data/
*.db
.env
.env.local
```

Do not commit runtime SQLite data or credentials.

## License

MIT

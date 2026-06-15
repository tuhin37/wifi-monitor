# Troubleshooting Guide

## Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No APs detected | Adapter not in monitor mode | `sudo iw dev wlan1 info` — should show `type monitor` |
| Kismet exits immediately | No compatible source found | Check logs: `docker compose logs kismet` |
| Exporter: "connection refused" | Kismet REST API not ready | Wait 30s, or check: `curl http://127.0.0.1:2501/session/check` |
| No data in Grafana | Prometheus not scraping exporter | Check `http://<host>:8501/metrics` |
| Dashboard shows "N/A" | No variables populated | Wait 1-2 polling cycles, or check Prometheus targets |
| High CPU on Pi | Too many devices tracked | Reduce `max_devices` in kismet_site.conf |
| Database growing too fast | Long retention + busy area | Reduce Prometheus retention: `PROMETHEUS_RETENTION=7d` |

## Detailed Troubleshooting

### 1. Kismet Can't See Any Devices

First, verify the adapter is actually capturing packets:

```bash
# Check monitor mode
iw dev wlan1 info

# Test packet capture (should show beacons/probes)
sudo tcpdump -i wlan1 -c 20 -n -e type mgt subtype beacon

# If no packets, driver may not support real monitor mode
# See docs/hardware.md for compatible adapters
```

If tcpdump shows packets but Kismet doesn't, check the Kismet logs:

```bash
docker compose logs kismet
```

Look for lines like:
- `opening source wlan1` — should say `SUCCESS`
- `no supported data sources found` — adapter or driver issue

### 2. Prometheus Not Scraping

```bash
# Check if exporter is serving metrics
curl http://127.0.0.1:8501/metrics | head -20

# Check Prometheus targets
curl http://127.0.0.1:9090/api/v1/targets | python3 -m json.tool
```

### 3. Grafana Shows No Data

```bash
# Check Grafana datasource
# Go to Configuration > Data Sources > Prometheus > "Test"

# Check if Prometheus has any data for the metrics
curl 'http://127.0.0.1:9090/api/v1/query?query=wifi_ap_signal_dbm'
```

### 4. Channel Utilization Not Showing

The channel utilization panel requires:
1. `WIFI_INTERFACE` set in `.env`
2. The `iw` tool installed on the host
3. The wireless driver must support `iw survey dump`

```bash
# Test iw survey
sudo iw dev wlan1 survey dump

# Look for lines with "channel time" and "channel time busy"
# If missing, the driver doesn't support survey data
```

### 5. Docker Permission Issues

```bash
# If you get "permission denied" for Docker
sudo usermod -aG docker $USER
# Log out and back in, or run: newgrp docker
```

### 6. Container Logs Are Too Large

```bash
# Truncate all container logs
sudo truncate -s 0 $(docker inspect --format='{{.LogPath}}' $(docker ps -q) 2>/dev/null)

# Limit future log size
# docker-compose.yml already has max-size: "10m" and max-file: "3"
```

### 7. "Too many open files" Error

Kismet tracks many devices and can exhaust file descriptors on long runs:

```bash
# Check current limits
ulimit -n

# Increase system limit
echo "fs.file-max = 65536" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Increase Docker container limits
# Add to docker run or compose:
#   ulimits:
#     nofile:
#       soft: 65536
#       hard: 65536
```

### 8. Grafana Login Issues

Default credentials: `admin` / `admin`

If you changed them in `.env` and forgot:
```bash
docker compose exec grafana grafana-cli admin reset-admin-password newpassword
```

### 9. Restarting Clean

```bash
# Full restart
docker compose down
docker compose up -d

# Full restart with data reset (WARNING: deletes all history)
docker compose down -v
docker compose up -d
```

## Getting Help

If you encounter issues not covered here:

1. Check Kismet documentation: https://www.kismetwireless.net/docs/
2. Collect logs: `docker compose logs --tail=100 > wifi-monitor-debug.log`
3. Open an issue at: https://github.com/tuhin37/wifi-monitor/issues

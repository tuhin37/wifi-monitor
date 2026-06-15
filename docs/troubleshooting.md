# Troubleshooting

| Symptom | Fix |
|---------|-----|
| No APs detected | `sudo iw dev wlan1 info` — must show `type monitor`. Run `./scripts/setup-monitor-mode.sh` |
| Kismet exits | `docker compose logs kismet`. Check adapter compatibility in docs/hardware.md |
| Exporter "connection refused" | `curl http://127.0.0.1:2501/session/check` — Kismet may not be ready yet |
| No metrics in Grafana | `curl http://<host>:8501/metrics` — verify exporter is serving data |
| Speed test fails | Check `MGMT_INTERFACE` has internet access and `speedtest-cli` is installed |
| Speed test "no interface" | The management interface needs to be up and have DHCP. Try `dhclient wlan0` |

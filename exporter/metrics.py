"""Prometheus metrics — all data points the exporter exposes."""

from prometheus_client import Counter, Gauge, Info, generate_latest


class Metrics:
    def __init__(self):
        # ---- AP / scanner ----
        self.ap_info = Info(
            "wifi_ap_info", "AP metadata", ["bssid", "ssid"])
        self.ap_signal_dbm = Gauge(
            "wifi_ap_signal_dbm", "RSSI dBm", ["bssid", "ssid", "type"])
        self.ap_snr = Gauge(
            "wifi_ap_snr_db", "SNR dB", ["bssid", "ssid"])
        self.ap_freq = Gauge(
            "wifi_ap_frequency_mhz", "Center freq MHz", ["bssid", "ssid"])
        self.ap_channel = Gauge(
            "wifi_ap_channel", "Channel number", ["bssid", "ssid"])
        self.ap_band = Gauge(
            "wifi_ap_band", "Band (1=2.4, 2=5, 3=6)", ["bssid", "ssid"])
        self.ap_count = Gauge(
            "wifi_ap_count", "AP count by band", ["band"])

        # ---- Speed test ----
        self.st_download = Gauge(
            "wifi_speedtest_download_bps", "Download bitrate",
            ["ssid", "bssid"])
        self.st_upload = Gauge(
            "wifi_speedtest_upload_bps", "Upload bitrate",
            ["ssid", "bssid"])
        self.st_ping = Gauge(
            "wifi_speedtest_ping_ms", "Ping latency ms",
            ["ssid", "bssid"])
        self.st_jitter = Gauge(
            "wifi_speedtest_jitter_ms", "Jitter ms",
            ["ssid", "bssid"])
        self.st_loss = Gauge(
            "wifi_speedtest_packet_loss", "Packet loss ratio",
            ["ssid", "bssid"])
        self.st_count = Counter(
            "wifi_speedtest_total", "Speed test count",
            ["ssid", "bssid", "status"])

        # ---- Scheduler ----
        self.task_count = Gauge(
            "wifi_scheduled_tasks_total", "Scheduled task count",
            ["status"])
        self.task_duration = Gauge(
            "wifi_task_duration_seconds", "Last task duration",
            ["task_id", "status"])

        # ---- Health ----
        self.scanner_up = Gauge(
            "wifi_scanner_up", "Scanner backend reachable")

    def update_aps(self, devices: list[dict]):
        bands = {}
        for d in devices:
            b = d.get("bssid", "").replace(":", "").lower()
            s = d.get("ssid", "_hidden").replace(" ", " ")
            t = d.get("type", "unknown")
            bnd = d.get("band", "unknown")
            bands[bnd] = bands.get(bnd, 0) + 1

            self.ap_signal_dbm.labels(bssid=b, ssid=s, type=t).set(d.get("signal_dbm", 0))
            self.ap_snr.labels(bssid=b, ssid=s).set(d.get("snr", 0))
            self.ap_freq.labels(bssid=b, ssid=s).set(d.get("frequency", 0))
            self.ap_channel.labels(bssid=b, ssid=s).set(d.get("channel", 0))
            band_val = {"2.4 GHz": 1, "5 GHz": 2, "6 GHz": 3}.get(bnd, 0)
            self.ap_band.labels(bssid=b, ssid=s).set(band_val)
        for band, count in bands.items():
            self.ap_count.labels(band=band).set(count)

    def update_speedtest(self, r: dict, ssid: str, bssid: str):
        b = bssid.replace(":", "").lower()[:8]
        s = ssid.replace(" ", "_")
        if r.get("success"):
            self.st_download.labels(ssid=s, bssid=b).set(r["download_mbps"] * 1_000_000)
            self.st_upload.labels(ssid=s, bssid=b).set(r["upload_mbps"] * 1_000_000)
            self.st_ping.labels(ssid=s, bssid=b).set(r["ping_ms"])
            self.st_jitter.labels(ssid=s, bssid=b).set(r["jitter_ms"])
            self.st_loss.labels(ssid=s, bssid=b).set(r["packet_loss"])
            self.st_count.labels(ssid=s, bssid=b, status="success").inc()
        else:
            self.st_count.labels(ssid=s, bssid=b, status="failed").inc()

    def generate(self) -> bytes:
        return generate_latest()

"""Prometheus metrics for Wi-Fi Monitor."""

from prometheus_client import Counter, Gauge, Info, generate_latest
from urllib.parse import quote


class Metrics:
    def __init__(self):
        # ---- AP / scanner ----
        self.ap_signal_dbm = Gauge(
            "wifi_ap_signal_dbm", "RSSI dBm", ["bssid", "ssid", "ssid_key", "type", "band", "freq"])
        self.ap_freq = Gauge(
            "wifi_ap_frequency_mhz", "Center freq MHz", ["bssid", "ssid"])
        self.ap_channel = Gauge(
            "wifi_ap_channel", "Channel number", ["bssid", "ssid"])
        self.ap_band = Gauge(
            "wifi_ap_band", "Band (1=2.4, 2=5, 3=6)", ["bssid", "ssid"])
        self.ap_count = Gauge(
            "wifi_ap_count", "AP count by band", ["band"])

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

            ssid_key = quote(s, safe="")
            self.ap_signal_dbm.labels(bssid=b, ssid=s, ssid_key=ssid_key, type=t, band=bnd, freq=str(d.get("frequency", ""))).set(d.get("signal_dbm", 0))
            self.ap_freq.labels(bssid=b, ssid=s).set(d.get("frequency", 0))
            self.ap_channel.labels(bssid=b, ssid=s).set(d.get("channel", 0))
            band_val = {"2.4 GHz": 1, "5 GHz": 2, "6 GHz": 3}.get(bnd, 0)
            self.ap_band.labels(bssid=b, ssid=s).set(band_val)
        for band, count in bands.items():
            self.ap_count.labels(band=band).set(count)

    def generate(self) -> bytes:
        return generate_latest()

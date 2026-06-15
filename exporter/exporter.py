#!/usr/bin/env python3
"""
WiFi Monitor Prometheus Exporter

Collects wireless network metrics from Kismet's REST API and exposes
them as Prometheus metrics for Grafana dashboarding.

Metrics exposed:
  - wifi_ap_info: Static AP metadata (channel, band, type, encryption, vendor)
  - wifi_ap_signal_dbm: RSSI signal strength per device
  - wifi_ap_snr_db: Signal-to-noise ratio per device
  - wifi_ap_channel_width: Estimated channel width in MHz
  - wifi_ap_packets_total: Packet count per device
  - wifi_ap_data_bytes_total: Data volume per device
  - wifi_ap_uptime_seconds: BSS uptime per device
  - wifi_ap_frequency_mhz: Operating frequency per device
  - wifi_ap_clients: Number of associated clients per AP
  - wifi_channel_utilization: Channel utilization % from iw survey dump

Required environment variables:
  KISMET_URL       - Kismet REST API URL (default: http://127.0.0.1:2501)
  KISMET_USERNAME  - Kismet REST username (default: admin)
  KISMET_PASSWORD  - Kismet REST password (default: admin)
  EXPORTER_PORT    - Prometheus metrics port (default: 8501)
  WIFI_INTERFACE   - Wireless interface for iw survey (optional)
  POLL_INTERVAL    - Kismet poll interval in seconds (default: 15)
"""

import os
import sys
import time
import json
import subprocess
import re
from datetime import datetime

from prometheus_client import start_http_server, Gauge, Counter, Info
from kismet_rest import KismetConnector, Devices
from channel_map import frequency_to_channel, frequency_to_band


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KISMET_URL = os.getenv("KISMET_URL", "http://127.0.0.1:2501")
KISMET_USERNAME = os.getenv("KISMET_USERNAME", "admin")
KISMET_PASSWORD = os.getenv("KISMET_PASSWORD", "admin")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "8501"))
WIFI_INTERFACE = os.getenv("WIFI_INTERFACE", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))

# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------

# --- Info/State (static metadata, set once per device) ---
wifi_ap_info = Info(
    "wifi_ap_info",
    "Static metadata for detected wireless devices",
    ["mac", "ssid", "type", "channel", "band", "encryption", "vendor", "first_seen"],
)

# --- Gauges (current values) ---
wifi_ap_signal_dbm = Gauge(
    "wifi_ap_signal_dbm",
    "Current RSSI signal strength in dBm",
    ["mac", "ssid", "type"],
)

wifi_ap_snr_db = Gauge(
    "wifi_ap_snr_db",
    "Current signal-to-noise ratio in dB",
    ["mac", "ssid", "type"],
)

wifi_ap_channel_width = Gauge(
    "wifi_ap_channel_width_mhz",
    "Channel width in MHz",
    ["mac", "ssid"],
)

wifi_ap_frequency_mhz = Gauge(
    "wifi_ap_frequency_mhz",
    "Operating center frequency in MHz",
    ["mac", "ssid"],
)

wifi_ap_uptime_seconds = Gauge(
    "wifi_ap_uptime_seconds",
    "BSS uptime in seconds",
    ["mac", "ssid"],
)

wifi_ap_clients = Gauge(
    "wifi_ap_clients",
    "Number of associated clients",
    ["mac", "ssid"],
)

# --- Counters (accumulating) ---
wifi_ap_packets_total = Counter(
    "wifi_ap_packets_total",
    "Total packets seen for device",
    ["mac", "ssid", "type"],
)

wifi_ap_data_bytes_total = Counter(
    "wifi_ap_data_bytes_total",
    "Total data bytes seen for device",
    ["mac", "ssid", "type"],
)

# --- Channel Utilization (from iw survey dump) ---
wifi_channel_utilization = Gauge(
    "wifi_channel_utilization_percent",
    "Channel utilization percentage from iw survey dump",
    ["interface", "channel", "band"],
)


# ---------------------------------------------------------------------------
# Kismet Data Collection
# ---------------------------------------------------------------------------

class WiFiCollector:
    """Collects and exports WiFi metrics from Kismet + iw survey."""

    def __init__(self):
        self._known_devices = {}  # mac -> metadata dict
        self._kismet_conn = KismetConnector(
            host_uri=KISMET_URL,
            username=KISMET_USERNAME,
            password=KISMET_PASSWORD,
        )
        self._devices_api = Devices(connector=self._kismet_conn)
        self._last_poll = int(datetime.utcnow().timestamp())
        print(f"[+] Connected to Kismet at {KISMET_URL}", flush=True)

    def collect_kismet_devices(self):
        """Poll Kismet for all devices seen since last poll."""
        now = int(datetime.utcnow().timestamp())
        try:
            # Get all devices (incremental if supported)
            devices = self._devices_api.all()
            self._last_poll = now
            return devices
        except Exception as e:
            print(f"[-] Kismet poll error: {e}", flush=True)
            return []

    def _parse_encryption(self, device) -> str:
        """Extract encryption type from Kismet device data."""
        try:
            encrypt = device.get("kismet.device.base.crypt", "")
            if isinstance(encrypt, str):
                return encrypt
            if isinstance(encrypt, (int, float)):
                return {0: "none", 1: "wep", 2: "wpa", 3: "wpa2", 4: "wpa3", 5: "wpa1+2",
                        6: "wpa2+3", 7: "wpa1+2+3"}.get(int(encrypt), f"unknown({encrypt})")
            return str(encrypt)
        except Exception:
            return "unknown"

    def _parse_dot11_device(self, device) -> dict:
        """Parse dot11-specific fields from a device."""
        info = {}
        try:
            dot11 = device.get("dot11.device", {})
            if dot11:
                # BSS timestamp (uptime)
                bss_ts = dot11.get("dot11.device.bss_timestamp", 0)
                if bss_ts:
                    info["uptime"] = bss_ts / 1000000  # microseconds -> seconds

                # Associated clients
                client_map = dot11.get("dot11.device.associated_client_map", {})
                if client_map:
                    info["num_clients"] = len(client_map)
                else:
                    info["num_clients"] = 0

                # Channel width from HT/VHT/HE capabilities
                ht_caps = dot11.get("dot11.device.ht_capabilities", {})
                vht_caps = dot11.get("dot11.device.vht_capabilities", {})
                he_caps = dot11.get("dot11.device.he_capabilities", {})

                if ht_caps:
                    # HT capabilities: 0=20MHz, 1=20/40MHz
                    chan_width = ht_caps.get("ht.ht_cap.chan_width_set", 0)
                    info["channel_width"] = 40 if chan_width else 20
                if vht_caps:
                    # VHT: max MPDU duration implies width support
                    vht_chan = vht_caps.get("vht.vht_cap.supported_chan_width", 0)
                    info["channel_width"] = 80 if vht_chan else (info.get("channel_width", 20))
                if he_caps:
                    # HE (Wi-Fi 6): 160/80+80 possible but hard to detect
                    info["channel_width"] = max(info.get("channel_width", 20), 20)

        except Exception:
            pass
        return info

    def process_devices(self, devices):
        """Process Kismet devices and update Prometheus metrics."""
        seen_macs = set()

        for device in devices:
            try:
                # Base device info
                mac = device.get("kismet.device.base.macaddr", "")
                if not mac:
                    continue
                seen_macs.add(mac)

                ssid = device.get("kismet.device.base.commonname", "(hidden)")
                dev_type = device.get("kismet.device.base.type", "unknown")
                vendor = device.get("kismet.device.base.manuf", "unknown")
                first_seen = device.get("kismet.device.base.first_time", 0)

                # Signal
                signal_info = device.get("kismet.device.base.signal", {})
                last_signal = signal_info.get("kismet.common.signal.last_signal", 0)
                last_noise = signal_info.get("kismet.common.signal.last_noise", 0)
                snr = last_signal - last_noise if last_signal and last_noise else 0
                max_signal = signal_info.get("kismet.common.signal.max_signal", 0)
                min_signal = signal_info.get("kismet.common.signal.min_signal", 0)

                # Frequency -> channel -> band
                freq = device.get("kismet.device.base.frequency", 0)
                channel = frequency_to_channel(freq)
                band = frequency_to_band(freq)

                # Encryption
                encryption = self._parse_encryption(device)

                # Dot11 details
                dot11_info = self._parse_dot11_device(device)
                uptime = dot11_info.get("uptime", 0)
                num_clients = dot11_info.get("num_clients", -1)
                channel_width = dot11_info.get("channel_width", 0)

                # Packets and data
                packets = device.get("kismet.device.base.packets", {}).get("total", 0)
                datasize = device.get("kismet.device.base.datasize", 0)

                # Sanitize SSID for Prometheus labels (no spaces/special chars)
                ssid_label = ssid.replace(" ", "_").replace('"', "").replace("\\", "")
                if not ssid_label:
                    ssid_label = "(hidden)"

                # Sanitize MAC for label
                mac_label = mac.replace(":", "").lower()

                # --- Set Prometheus metrics ---

                # Info (static metadata) - set once per device
                if mac not in self._known_devices:
                    wifi_ap_info.labels(
                        mac=mac_label,
                        ssid=ssid_label,
                        type=dev_type,
                        channel=str(channel),
                        band=band,
                        encryption=encryption,
                        vendor=vendor,
                        first_seen=str(first_seen),
                    ).info({
                        "mac": mac,
                        "ssid": ssid,
                        "type": dev_type,
                        "channel": str(channel),
                        "band": band,
                        "encryption": encryption,
                        "vendor": vendor,
                        "first_seen": str(first_seen),
                    })
                    self._known_devices[mac] = {
                        "ssid": ssid_label,
                        "type": dev_type,
                    }

                # Signal strength (always updated)
                wifi_ap_signal_dbm.labels(
                    mac=mac_label,
                    ssid=ssid_label,
                    type=dev_type,
                ).set(last_signal)

                # SNR
                wifi_ap_snr_db.labels(
                    mac=mac_label,
                    ssid=ssid_label,
                    type=dev_type,
                ).set(snr)

                # Channel width
                if channel_width:
                    wifi_ap_channel_width.labels(
                        mac=mac_label,
                        ssid=ssid_label,
                    ).set(channel_width)

                # Frequency
                if freq:
                    wifi_ap_frequency_mhz.labels(
                        mac=mac_label,
                        ssid=ssid_label,
                    ).set(freq)

                # Uptime
                if uptime:
                    wifi_ap_uptime_seconds.labels(
                        mac=mac_label,
                        ssid=ssid_label,
                    ).set(uptime)

                # Associated clients
                if num_clients >= 0:
                    wifi_ap_clients.labels(
                        mac=mac_label,
                        ssid=ssid_label,
                    ).set(num_clients)

                # Packet/data counters (incremental via Prometheus counter)
                wifi_ap_packets_total.labels(
                    mac=mac_label,
                    ssid=ssid_label,
                    type=dev_type,
                ).inc(packets)

                wifi_ap_data_bytes_total.labels(
                    mac=mac_label,
                    ssid=ssid_label,
                    type=dev_type,
                ).inc(datasize)

            except Exception as e:
                print(f"[-] Error processing device {device.get('kismet.device.base.macaddr', '?')}: {e}", flush=True)
                continue

        # Clean up stale devices (not seen in this poll)
        # Prometheus client doesn't support removing metrics easily,
        # so stale devices remain in the metric set until exporter restart.
        # This is acceptable for monitoring purposes.

    def collect_iw_survey(self):
        """Collect channel utilization from iw survey dump."""
        if not WIFI_INTERFACE:
            return

        try:
            result = subprocess.run(
                ["iw", "dev", WIFI_INTERFACE, "survey", "dump"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return

            output = result.stdout
            # Parse iw survey dump output
            blocks = output.strip().split("\n\n")
            for block in blocks:
                if "in use" not in block and "no survey data" in block:
                    continue

                freq_match = re.search(r"in use\s+(\d+)\s+MHz", block)
                chan_match = re.search(r"channel:\s+(\d+)", block)
                time_match = re.search(r"channel time:\s+(\d+)", block)
                busy_match = re.search(r"channel time busy:\s+(\d+)", block)

                if freq_match and time_match and busy_match:
                    freq = int(freq_match.group(1))
                    channel = frequency_to_channel(freq)
                    band = frequency_to_band(freq)
                    total_time = int(time_match.group(1))
                    busy_time = int(busy_match.group(1))

                    if total_time > 0:
                        util_pct = round((busy_time / total_time) * 100, 1)
                        wifi_channel_utilization.labels(
                            interface=WIFI_INTERFACE,
                            channel=str(channel),
                            band=band,
                        ).set(util_pct)

        except FileNotFoundError:
            # iw not installed
            pass
        except subprocess.TimeoutExpired:
            print("[-] iw survey dump timed out", flush=True)
        except Exception as e:
            print(f"[-] iw survey error: {e}", flush=True)

    def run_forever(self):
        """Main collection loop."""
        print(f"[+] WiFi Monitor Exporter starting on port {EXPORTER_PORT}", flush=True)
        print(f"[+] Polling Kismet every {POLL_INTERVAL}s", flush=True)
        if WIFI_INTERFACE:
            print(f"[+] iw survey interface: {WIFI_INTERFACE}", flush=True)
        else:
            print("[!] No WIFI_INTERFACE set - channel utilization disabled", flush=True)

        while True:
            devices = self.collect_kismet_devices()
            if devices:
                self.process_devices(devices)
                print(f"[+] Collected {len(devices)} devices from Kismet", flush=True)
            else:
                print("[.] No new device data from Kismet", flush=True)

            self.collect_iw_survey()
            time.sleep(POLL_INTERVAL)


def main():
    collector = WiFiCollector()
    start_http_server(EXPORTER_PORT)
    try:
        collector.run_forever()
    except KeyboardInterrupt:
        print("\n[+] Shutting down", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()

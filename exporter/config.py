"""Application configuration loaded from config.yml and environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ScannerConfig(BaseModel):
    backend: str = "kismet"           # "kismet" or "iw"
    interface: str = "wlan1"          # monitor-mode interface
    kismet_url: str = "http://127.0.0.1:2501"
    kismet_username: str = "admin"
    kismet_password: str = "<changeme>"
    poll_interval: int = 15


class WiFiConfig(BaseModel):
    management_interface: str = "wlan0"
    backend: str = "nmcli"            # "nmcli" or "wpa_supplicant"


class SpeedTestConfig(BaseModel):
    backend: str = "speedtest-cli"    # "speedtest-cli" or "iperf3"
    iperf3_server: str = ""
    timeout: int = 60


class SchedulerConfig(BaseModel):
    enabled: bool = True
    default_schedule: str = "0 */6 * * *"


class ExporterConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8501
    data_dir: str = "/data"


class Config(BaseModel):
    exporter: ExporterConfig = Field(default_factory=ExporterConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    wifi: WiFiConfig = Field(default_factory=WiFiConfig)
    speedtest: SpeedTestConfig = Field(default_factory=SpeedTestConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        cfg = cls()
        if path is None:
            candidates = [
                os.environ.get("CONFIG_PATH", ""),
                "/etc/wifi-monitor/config.yml",
                str(Path.cwd() / "config.yml"),
            ]
            path = next((p for p in candidates if p and os.path.exists(p)), None)
        if path:
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            cfg = cls(**raw)
        # Env overrides
        if os.environ.get("EXPORTER_PORT"):
            cfg.exporter.port = int(os.environ["EXPORTER_PORT"])
        if os.environ.get("DATA_DIR"):
            cfg.exporter.data_dir = os.environ["DATA_DIR"]
        if os.environ.get("SCANNER_INTERFACE"):
            cfg.scanner.interface = os.environ["SCANNER_INTERFACE"]
        if os.environ.get("SCANNER_BACKEND"):
            cfg.scanner.backend = os.environ["SCANNER_BACKEND"]
        if os.environ.get("KISMET_URL"):
            cfg.scanner.kismet_url = os.environ["KISMET_URL"]
        if os.environ.get("KISMET_USERNAME"):
            cfg.scanner.kismet_username = os.environ["KISMET_USERNAME"]
        if os.environ.get("KISMET_PASSWORD"):
            cfg.scanner.kismet_password = os.environ["KISMET_PASSWORD"]
        if os.environ.get("MGMT_INTERFACE"):
            cfg.wifi.management_interface = os.environ["MGMT_INTERFACE"]
        if os.environ.get("WIFI_BACKEND"):
            cfg.wifi.backend = os.environ["WIFI_BACKEND"]
        if os.environ.get("SPEEDTEST_BACKEND"):
            cfg.speedtest.backend = os.environ["SPEEDTEST_BACKEND"]
        if os.environ.get("IPERF3_SERVER"):
            cfg.speedtest.iperf3_server = os.environ["IPERF3_SERVER"]
        if os.environ.get("POLL_INTERVAL"):
            cfg.scanner.poll_interval = int(os.environ["POLL_INTERVAL"])
        return cfg

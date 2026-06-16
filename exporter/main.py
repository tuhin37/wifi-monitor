"""Wi-Fi Monitor Exporter — Main Entry Point.

Runs:
1. Prometheus HTTP server (exposes /metrics)
2. Background scanner loop (polls Kismet or runs iw scan)
"""

import asyncio
import logging
import os
import signal
import sys
import time

from prometheus_client import start_http_server

from config import Config
from database import Database
from scanner import Scanner
from metrics import Metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("wifi-monitor")

class App:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(os.path.join(config.exporter.data_dir, "wifi_monitor.db"))
        self.metrics = Metrics()
        self.scanner = Scanner(config)
        self._running = True
        self._bring_up_interface()

    @staticmethod
    def _bring_up_interface():
        import subprocess
        try:
            subprocess.run(["ip", "link", "set", "wlp5s0", "up"], check=False, capture_output=True)
        except FileNotFoundError:
            pass  # ip not available, hope the host has it up

    async def scanner_loop(self):
        logger.info("Scanner loop started (backend=%s, interface=%s, interval=%ds)",
                     self.config.scanner.backend, self.config.scanner.interface,
                     self.config.scanner.poll_interval)
        while self._running:
            try:
                devices = await self.scanner.scan()
                if devices is not None:
                    for d in devices:
                        if "bssid" in d:
                            self.db.upsert_ap(d["bssid"], d)
                    self.metrics.update_aps(devices)
                    self.metrics.scanner_up.set(1)
                    logger.debug("Scanned %d devices", len(devices))
                else:
                    self.metrics.scanner_up.set(0)
            except Exception as e:
                logger.error("Scan loop error: %s", e)
                self.metrics.scanner_up.set(0)
            await asyncio.sleep(self.config.scanner.poll_interval)

    async def run(self):
        start_http_server(self.config.exporter.port)
        logger.info("Prometheus metrics at http://%s:%d/metrics", self.config.exporter.host, self.config.exporter.port)
        await self.scanner_loop()

def main():
    config = Config.load(os.environ.get("CONFIG_PATH") or None)
    app = App(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    def _shutdown():
        app._running = False
        loop.call_later(3, loop.stop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError: pass
    try: loop.run_until_complete(app.run())
    except KeyboardInterrupt: _shutdown()
    finally: loop.close()

if __name__ == "__main__":
    main()

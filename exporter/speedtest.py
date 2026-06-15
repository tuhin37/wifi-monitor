"""Speed test runner — speedtest-cli or iperf3."""

import asyncio
import json
import logging
import shutil

logger = logging.getLogger(__name__)


class SpeedTestResult:
    def __init__(self):
        self.download_mbps = self.upload_mbps = 0.0
        self.ping_ms = self.jitter_ms = 0.0
        self.packet_loss = 0.0
        self.server_name = self.server_location = ""
        self.success = False
        self.error = ""

    def to_dict(self) -> dict:
        return {
            "download_mbps": round(self.download_mbps, 2),
            "upload_mbps": round(self.upload_mbps, 2),
            "ping_ms": round(self.ping_ms, 2),
            "jitter_ms": round(self.jitter_ms, 2),
            "packet_loss": self.packet_loss,
            "server_name": self.server_name,
            "server_location": self.server_location,
            "success": self.success,
            "error": self.error,
        }


class SpeedTestRunner:
    def __init__(self, backend: str = "speedtest-cli",
                 iperf3_server: str = "", timeout: int = 60):
        self.backend = backend
        self.iperf3_server = iperf3_server
        self.timeout = timeout

    async def run(self, interface: str = "") -> SpeedTestResult:
        if self.backend == "iperf3":
            return await self._iperf3()
        return await self._speedtest_cli()

    async def _speedtest_cli(self) -> SpeedTestResult:
        r = SpeedTestResult()
        cmd = shutil.which("speedtest") or shutil.which("speedtest-cli") or ""
        if not cmd:
            r.error = "speedtest-cli not found"
            return r
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, "--format", "json", "--accept-license", "--accept-gdpr",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            if proc.returncode != 0:
                r.error = stderr.decode().strip()[:200]
                return r
            data = json.loads(stdout.decode())
            r.download_mbps = data.get("download", {}).get("bandwidth", 0) / 125000
            r.upload_mbps = data.get("upload", {}).get("bandwidth", 0) / 125000
            r.ping_ms = data.get("ping", {}).get("latency", 0)
            r.jitter_ms = data.get("ping", {}).get("jitter", 0)
            r.packet_loss = data.get("packetLoss", 0)
            svr = data.get("server", {})
            r.server_name = svr.get("name", "")
            r.server_location = f"{svr.get('location','')}, {svr.get('country','')}"
            r.success = True
            logger.info("Speedtest: %.1f↓ %.1f↑ %.1fms", r.download_mbps, r.upload_mbps, r.ping_ms)
        except asyncio.TimeoutError:
            r.error = "timed out"
        except Exception as e:
            r.error = str(e)
        return r

    async def _iperf3(self) -> SpeedTestResult:
        r = SpeedTestResult()
        if not self.iperf3_server or not shutil.which("iperf3"):
            r.error = "iperf3 not configured"
            return r
        try:
            for flag, attr in [([], "download_mbps"), (["-R"], "upload_mbps")]:
                proc = await asyncio.create_subprocess_exec(
                    "iperf3", "-c", self.iperf3_server, "-t", "10", "-J", *flag,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                if proc.returncode == 0:
                    data = json.loads(stdout.decode())
                    bps = data.get("end", {}).get("sum_received", {}).get("bits_per_second", 0)
                    setattr(r, attr, bps / 1_000_000)
                    if not r.ping_ms:
                        r.ping_ms = data.get("start", {}).get("connected", [{}])[0].get("remote_host", "")
            r.success = True
        except asyncio.TimeoutError:
            r.error = "iperf3 timed out"
        except Exception as e:
            r.error = str(e)
        return r

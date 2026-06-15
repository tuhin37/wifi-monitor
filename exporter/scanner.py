"""Wi-Fi scanner — Kismet REST API or built-in iw scan."""

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

FREQ_TO_CHANNEL = {}
for ch, f in enumerate([2412,2417,2422,2427,2432,2437,2442,2447,
                        2452,2457,2462,2467,2472,2484], start=1):
    FREQ_TO_CHANNEL[f] = ch

_5g = [(36,5180),(38,5190),(40,5200),(42,5210),(44,5220),(46,5230),(48,5240),
       (52,5260),(56,5280),(60,5300),(64,5320),
       (100,5500),(104,5520),(108,5540),(112,5560),(116,5580),(120,5600),(124,5620),(128,5640),
       (132,5660),(136,5680),(140,5700),(144,5720),
       (149,5745),(153,5765),(157,5785),(161,5805),(165,5825)]
for ch, f in _5g:
    FREQ_TO_CHANNEL[f] = ch


def freq_to_channel(freq: int) -> int:
    if freq in FREQ_TO_CHANNEL:
        return FREQ_TO_CHANNEL[freq]
    best = min(FREQ_TO_CHANNEL, key=lambda f: abs(f - freq), default=0)
    return FREQ_TO_CHANNEL[best] if best and abs(best - freq) <= 10 else 0


def freq_to_band(freq: int) -> str:
    if 2400 <= freq <= 2500:
        return "2.4 GHz"
    if 5150 <= freq <= 5900:
        return "5 GHz"
    if 5925 <= freq <= 7125:
        return "6 GHz"
    return "unknown"


class IWScanner:
    def __init__(self, interface: str):
        self.interface = interface

    async def scan(self) -> list[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", self.interface, "scan",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                logger.warning("iw scan: %s", stderr.decode().strip())
                return []
            return self._parse(stdout.decode())
        except asyncio.TimeoutError:
            logger.error("iw scan timed out")
        except FileNotFoundError:
            logger.error("iw not found")
        return []

    def _parse(self, output: str) -> list[dict]:
        devices = []
        for block in re.split(r'\nBSS ', output)[1:]:
            ap = {"type": "Wi-Fi AP"}
            m = re.match(r'([0-9a-f:]{17})', block)
            if not m:
                continue
            ap["bssid"] = m.group(1).lower()
            m = re.search(r'SSID: (.+)', block)
            if m:
                raw_ssid = m.group(1).strip()
                # Filter out hidden/null SSIDs
                if raw_ssid and not all(c == '\x00' for c in raw_ssid) and not raw_ssid.startswith('\\x00'):
                    ap["ssid"] = raw_ssid
                else:
                    ap["ssid"] = "(hidden)"
            else:
                ap["ssid"] = "(hidden)"
            m = re.search(r'freq: (\d+)', block)
            if m:
                f = int(m.group(1))
                ap["frequency"] = f
                ap["channel"] = freq_to_channel(f)
                ap["band"] = freq_to_band(f)
            m = re.search(r'signal: (-?\d+\.?\d*) dBm', block)
            if m:
                ap["signal_dbm"] = float(m.group(1))
            m = re.search(r'width: (\d+)', block)
            if m:
                ap["width_mhz"] = int(m.group(1))
            ap["encryption"] = "WPA2" if 'RSN' in block else ("WPA" if 'WPA' in block else "open")
            devices.append(ap)
        return devices


class KismetScanner:
    def __init__(self, url: str, username: str, password: str):
        self.url = url
        self.auth = (username, password)

    async def scan(self) -> list[dict]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.url}/devices/last-time/0/devices.json", auth=self.auth)
                resp.raise_for_status()
                return self._parse(resp.json())
        except httpx.ConnectError:
            logger.warning("Kismet not reachable at %s", self.url)
        except Exception as e:
            logger.error("Kismet poll: %s", e)
        return []

    def _parse(self, raw: list) -> list[dict]:
        parsed = []
        for dev in raw:
            ap = {"type": dev.get("kismet.device.base.type", "unknown")}
            bssid = dev.get("kismet.device.base.macaddr", "")
            if not bssid:
                continue
            ap["bssid"] = bssid.lower()
            ap["ssid"] = dev.get("kismet.device.base.commonname", "(hidden)")
            ap["vendor"] = dev.get("kismet.device.base.manuf", "")
            sig = dev.get("kismet.device.base.signal", {}) or {}
            ap["signal_dbm"] = sig.get("kismet.common.signal.last_signal", 0)
            noise = sig.get("kismet.common.signal.last_noise", 0)
            ap["snr"] = ap["signal_dbm"] - noise if ap["signal_dbm"] and noise else 0
            freq = dev.get("kismet.device.base.frequency", 0)
            ap["frequency"] = freq
            ap["channel"] = freq_to_channel(freq)
            ap["band"] = freq_to_band(freq)
            ap["encryption"] = str(dev.get("kismet.device.base.crypt", "unknown"))
            ap["packets"] = dev.get("kismet.device.base.packets", {}).get("total", 0)
            ap["datasize"] = dev.get("kismet.device.base.datasize", 0)
            parsed.append(ap)
        return parsed


class Scanner:
    def __init__(self, config):
        self.config = config
        self.backend = config.scanner.backend
        if self.backend == "iw":
            self._impl = IWScanner(config.scanner.interface)
        else:
            self._impl = KismetScanner(
                config.scanner.kismet_url,
                config.scanner.kismet_username,
                config.scanner.kismet_password,
            )

    async def scan(self) -> list[dict]:
        return await self._impl.scan() or []

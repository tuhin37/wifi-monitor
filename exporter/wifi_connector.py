"""Wi-Fi connection manager — nmcli or wpa_supplicant backends."""

import asyncio
import logging
import re
import shutil

logger = logging.getLogger(__name__)


class WiFiConnector:
    def __init__(self, interface: str, backend: str = "nmcli"):
        self.interface = interface
        self.backend = backend

    async def connect(self, ssid: str, password: str = "") -> dict:
        if self.backend == "nmcli":
            return await self._nmcli_connect(ssid, password)
        return await self._wpa_connect(ssid, password)

    async def disconnect(self) -> dict:
        if self.backend == "nmcli":
            return await self._nmcli_disconnect()
        return await self._wpa_disconnect()

    async def status(self) -> dict:
        proc = await asyncio.create_subprocess_exec(
            "iw", "dev", self.interface, "link",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        if "Not connected" in output:
            return {"connected": False, "interface": self.interface}
        ssid_m = re.search(r"SSID: (.+)", output)
        sig_m = re.search(r"signal: (-?\d+)", output)
        freq_m = re.search(r"freq: (\d+)", output)
        return {
            "connected": True,
            "ssid": ssid_m.group(1).strip() if ssid_m else "",
            "signal": sig_m.group(1) if sig_m else "",
            "frequency": freq_m.group(1) if freq_m else "",
            "interface": self.interface,
        }

    # ---- nmcli ----
    async def _nmcli_connect(self, ssid: str, password: str = "") -> dict:
        if not shutil.which("nmcli"):
            return {"success": False, "message": "nmcli not found"}
        await self._nmcli_disconnect()
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "ifname", self.interface]
        if password:
            cmd += ["password", password]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            await asyncio.sleep(3)
            return {"success": True, "message": f"Connected to {ssid}"}
        return {"success": False, "message": stderr.decode().strip()[:200]}

    async def _nmcli_disconnect(self) -> dict:
        if not shutil.which("nmcli"):
            return {"success": False, "message": "nmcli not found"}
        proc = await asyncio.create_subprocess_exec(
            "nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        for line in stdout.decode().splitlines():
            parts = line.split(":")
            if len(parts) == 2 and parts[1] == self.interface:
                await asyncio.create_subprocess_exec(
                    "nmcli", "connection", "down", parts[0],
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return {"success": True, "message": "disconnected"}

    # ---- wpa_supplicant ----
    async def _wpa_connect(self, ssid: str, password: str = "") -> dict:
        if not shutil.which("wpa_cli"):
            return {"success": False, "message": "wpa_cli not found"}
        if password:
            conf = (
                'network={\n'
                '    ssid="' + ssid + '"\n'
                '    psk="' + password + '"\n'
                '    key_mgmt=WPA-PSK\n'
                '}\n'
            )
        else:
            conf = (
                'network={\n'
                '    ssid="' + ssid + '"\n'
                '    key_mgmt=NONE\n'
                '}\n'
            )
        conf_path = f"/tmp/wifimon_{self.interface}.conf"
        with open(conf_path, "w") as f:
            f.write(conf)
        await self._wpa_disconnect()
        await asyncio.create_subprocess_exec("ip", "link", "set", self.interface, "down")
        await asyncio.create_subprocess_exec("ip", "link", "set", self.interface, "up")
        wp = await asyncio.create_subprocess_exec(
            "wpa_supplicant", "-B", "-i", self.interface, "-c", conf_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await wp.wait()
        await asyncio.sleep(2)
        dhcp = await asyncio.create_subprocess_exec(
            "dhclient", "-v", self.interface,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(dhcp.wait(), timeout=15)
            return {"success": True, "message": f"Connected to {ssid}"}
        except asyncio.TimeoutError:
            dhcp.kill()
            return {"success": False, "message": "DHCP timed out"}

    async def _wpa_disconnect(self) -> dict:
        await asyncio.create_subprocess_exec(
            "pkill", "-f", f"wpa_supplicant.*{self.interface}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.create_subprocess_exec(
            "pkill", "-f", f"dhclient.*{self.interface}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return {"success": True, "message": "disconnected"}

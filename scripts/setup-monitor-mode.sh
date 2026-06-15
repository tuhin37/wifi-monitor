#!/usr/bin/env bash
# Enable monitor mode on a wireless interface.
# Usage: sudo ./scripts/setup-monitor-mode.sh <interface>
set -euo pipefail
IFACE="${1:-}"
if [ -z "$IFACE" ]; then
    echo "Usage: $0 <interface>"
    iw dev 2>/dev/null | awk '/Interface/{print "  " $2}'
    exit 1
fi
if [ "$EUID" -ne 0 ]; then echo "Run as root."; exit 1; fi
iw dev "$IFACE" info &>/dev/null || { echo "Interface $IFACE not found"; exit 1; }
echo "[*] Setting $IFACE to monitor mode..."
ip link set "$IFACE" down
iw dev "$IFACE" set type monitor 2>/dev/null || {
    echo "[!] iw failed, trying airmon-ng..."
    airmon-ng start "$IFACE" 2>/dev/null || { echo "Failed."; exit 1; }
}
ip link set "$IFACE" up
iw dev "$IFACE" info | grep -q "type monitor" && echo "[✓] $IFACE is in MONITOR mode" || echo "[-] Failed"

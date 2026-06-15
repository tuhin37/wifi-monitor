#!/usr/bin/env bash
# =============================================================================
# Setup Monitor Mode for a Wireless Interface
# =============================================================================
# Usage: sudo ./scripts/setup-monitor-mode.sh <interface>
#
# Example: sudo ./scripts/setup-monitor-mode.sh wlan1
#
# This script puts a wireless interface into monitor mode, which is required
# for Kismet to passively capture Wi-Fi frames.
#
# Requirements:
#   - iw and airmon-ng (aircrack-ng suite) installed
#   - A compatible wireless NIC (see docs/hardware.md)
#   - Root privileges
#
# Options:
#   -c, --check    Only check if interface supports monitor mode, don't enable
#   -h, --help     Show this help
# =============================================================================

set -euo pipefail

CHECK_ONLY=false
INTERFACE=""

usage() {
    sed -n 's/^# //p; s/^#$//p' "$0"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--check) CHECK_ONLY=true; shift ;;
        -h|--help) usage ;;
        -*) echo "Unknown option: $1"; usage ;;
        *) INTERFACE="$1"; shift ;;
    esac
done

if [ -z "$INTERFACE" ]; then
    echo "Error: No interface specified."
    echo "Usage: $0 <interface> [options]"
    echo "Available interfaces:"
    iw dev 2>/dev/null | awk '/Interface/{print $2}'
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)."
    exit 1
fi

# Check if interface exists
if ! iw dev "$INTERFACE" info &>/dev/null; then
    echo "Error: Interface '$INTERFACE' not found."
    echo "Available interfaces:"
    iw dev 2>/dev/null | awk '/Interface/{print $2}'
    exit 1
fi

# Check monitor mode support
echo "[*] Checking interface: $INTERFACE"

# Check driver info
DRIVER=$(ethtool -i "$INTERFACE" 2>/dev/null | grep driver | awk '{print $2}' || echo "unknown")
echo "[*] Driver: $DRIVER"

# Check current mode
CURRENT_MODE=$(iw dev "$INTERFACE" info 2>/dev/null | awk '/type/{print $2}')
echo "[*] Current mode: $CURRENT_MODE"

# Check if interface supports monitor mode
SUPPORTS_MONITOR=false
for mode in $(iw phy "$(iw dev "$INTERFACE" info 2>/dev/null | awk '/wiphy/{print $2}')" info 2>/dev/null | grep -i "monitor" || true); do
    if [ "$mode" = "monitor" ]; then
        SUPPORTS_MONITOR=true
        break
    fi
done

if [ "$SUPPORTS_MONITOR" = false ]; then
    echo "[!] Interface may not support monitor mode natively."
    echo "    Some USB adapters (e.g. RTL8812AU, AR9271) support it via special drivers."
    echo "    See docs/hardware.md for compatible adapters."
fi

echo "[*] Supports monitor mode: $SUPPORTS_MONITOR"

if [ "$CHECK_ONLY" = true ]; then
    echo "[✓] Check complete."
    exit 0
fi

# If already in monitor mode, nothing to do
if [ "$CURRENT_MODE" = "monitor" ]; then
    echo "[✓] Interface already in monitor mode."
    exit 0
fi

# Attempt to enable monitor mode
echo "[*] Bringing interface down..."
ip link set "$INTERFACE" down

echo "[*] Setting monitor mode..."
iw dev "$INTERFACE" set type monitor 2>/dev/null || {
    echo "[!] iw set type monitor failed. Trying airmon-ng..."
    if command -v airmon-ng &>/dev/null; then
        airmon-ng start "$INTERFACE" 2>/dev/null || {
            echo "[-] airmon-ng also failed."
            ip link set "$INTERFACE" up
            exit 1
        }
    else
        echo "[-] airmon-ng not found. Install aircrack-ng or use a different adapter."
        ip link set "$INTERFACE" up
        exit 1
    fi
}

echo "[*] Bringing interface up..."
ip link set "$INTERFACE" up

echo "[*] Verifying monitor mode..."
VERIFIED_MODE=$(iw dev "$INTERFACE" info 2>/dev/null | awk '/type/{print $2}')
if [ "$VERIFIED_MODE" = "monitor" ]; then
    echo "[✓] $INTERFACE is now in MONITOR mode."
    echo ""
    echo "    Next steps:"
    echo "    1. Edit .env and set WIFI_INTERFACE=$INTERFACE"
    echo "    2. Start the stack: docker compose up -d"
    echo "    3. Access Grafana at http://<host-ip>:3000"
    echo ""
    echo "    To revert: sudo ip link set $INTERFACE down; sudo iw dev $INTERFACE set type managed; sudo ip link set $INTERFACE up"
else
    echo "[-] Failed to set monitor mode. Current mode: $VERIFIED_MODE"
    exit 1
fi

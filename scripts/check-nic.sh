#!/usr/bin/env bash
# Check a wireless NIC's compatibility with monitor mode.
# Usage: ./scripts/check-nic.sh [interface]
set -euo pipefail
IFACE="${1:-}"
check() {
    local iface="$1"
    echo "--- $iface ---"
    iw dev "$iface" info 2>/dev/null || { echo "  Not found"; return; }
    echo "  Driver: $(ethtool -i "$iface" 2>/dev/null | grep driver | awk '{print $2}' || echo unknown)"
    echo "  Mode: $(iw dev "$iface" info | awk '/type/{print $2}')"
    phy=$(iw dev "$iface" info | awk '/wiphy/{print $2}')
    if iw phy "phy$phy" info 2>/dev/null | grep -q "monitor"; then
        echo "  Monitor: YES ✓"
    else
        echo "  Monitor: NO ✗"
    fi
    echo ""
}
if [ -n "$IFACE" ]; then check "$IFACE"; else
    for iface in $(iw dev 2>/dev/null | awk '/Interface/{print $2}'); do check "$iface"; done
fi

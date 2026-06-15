#!/usr/bin/env bash
# =============================================================================
# Check Wireless NIC Compatibility
# =============================================================================
# Usage: ./scripts/check-nic.sh [interface]
#
# Detects wireless interfaces, checks driver/chipset, and reports whether
# they are suitable for monitor mode with Kismet.
# =============================================================================

set -euo pipefail

INTERFACE="${1:-}"

echo "========================================"
echo " WiFi NIC Compatibility Check"
echo "========================================"
echo ""

detect_all() {
    echo "[*] Detected wireless interfaces:"
    iw dev 2>/dev/null | awk '/Interface/{print "  - " $2}' | while read -r iface; do
        echo "$iface"
    done
    echo ""
}

check_interface() {
    local IFACE="$1"
    echo "--- Checking: $IFACE ---"

    if ! iw dev "$IFACE" info &>/dev/null; then
        echo "  Status: NOT FOUND"
        return
    fi

    # Driver
    DRIVER=$(ethtool -i "$IFACE" 2>/dev/null | grep driver | awk '{print $2}' || echo "unknown")
    echo "  Driver: $DRIVER"

    # Mode
    MODE=$(iw dev "$IFACE" info 2>/dev/null | awk '/type/{print $2}')
    echo "  Current Mode: $MODE"

    # MAC
    MAC=$(iw dev "$IFACE" info 2>/dev/null | awk '/addr/{print $2}' || ip link show "$IFACE" | awk '/ether/{print $2}')
    echo "  MAC: $MAC"

    # PHY
    PHY=$(iw dev "$IFACE" info 2>/dev/null | awk '/wiphy/{print $2}')
    echo "  PHY: phy$PHY"

    # Monitor mode support
    SUPPORTS_MON=false
    if [ -n "$PHY" ]; then
        if iw phy "phy$PHY" info 2>/dev/null | grep -q "monitor"; then
            SUPPORTS_MON=true
        fi
    fi
    echo "  Monitor Mode: $([ "$SUPPORTS_MON" = true ] && echo 'YES ✓' || echo 'NO - may need special driver ✗')"

    # Supported bands
    echo "  Supported Bands:"
    if [ -n "$PHY" ]; then
        iw phy "phy$PHY" info 2>/dev/null | grep -A1 "Band" | grep -v "^--$" | while read -r line; do
            echo "    $line"
        done
    fi

    echo ""
}

# Compatibility notes function
show_notes() {
    echo "========================================"
    echo " Compatibility Notes"
    echo "========================================"
    echo ""
    echo "  GOOD (native monitor mode support):"
    echo "    - Atheros AR9271 (USB) - best for Raspberry Pi"
    echo "    - Atheros AR9580/AR9380 (PCIe)"
    echo "    - Intel AX200/AX210 (requires kernel module options)"
    echo "    - Ralink RT3070/RT3572 (USB)"
    echo ""
    echo "  OK (requires special driver):"
    echo "    - Realtek RTL8812AU (USB) - install rtl8812au-dkms"
    echo "    - Realtek RTL8814AU (USB) - install rtl8814au-dkms"
    echo "    - MediaTek MT7612U (USB) - in-kernel driver, varies"
    echo ""
    echo "  NOT RECOMMENDED (no/fake monitor):"
    echo "    - Broadcom BCM43xx (most chips) - limited support"
    echo "    - Realtek RTL8188CUS - fake monitor mode (no frame capture)"
    echo "    - Built-in WiFi on Raspberry Pi (brcmfmac) - no monitor mode"
    echo ""
    echo "  See docs/hardware.md for full details."
    echo "========================================"
}

if [ -n "$INTERFACE" ]; then
    check_interface "$INTERFACE"
else
    detect_all
    # Check each interface
    for iface in $(iw dev 2>/dev/null | awk '/Interface/{print $2}'); do
        check_interface "$iface"
    done
fi

show_notes

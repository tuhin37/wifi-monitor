# Supported Wi-Fi Hardware

This guide covers Wi-Fi adapters known to work with monitor mode and Kismet for passive scanning.

## How Monitor Mode Works

Monitor mode allows a Wi-Fi adapter to capture **all** 802.11 frames in range, not just those addressed to it. This is fundamentally different from normal "station" mode where the adapter only receives frames for networks it's associated with.

Kismet needs **one adapter in monitor mode** per band you want to monitor simultaneously.

## Adapter Selection Guide

### Tier 1: Recommended (Proven, Reliable)

| Adapter | Chipset | Interface | Bands | Max Channel Width | Price | Notes |
|---------|---------|-----------|-------|-------------------|-------|-------|
| Alfa AWUS036ACHM | RTL8812AU | USB 3.0 | 2.4 + 5 GHz | 80 MHz | ~$50 | Excellent all-rounder. Needs driver install. |
| Alfa AWUS036ACH | AR9271 | USB 2.0 | 2.4 GHz only | 20 MHz | ~$40 | Works out of box on Linux. Great for 2.4 GHz only. |
| Alfa AWUS1900 | RTL8814AU | USB 3.0 | 2.4 + 5 GHz | 80 MHz | ~$70 | Higher gain, 4x4 MIMO |
| Panda Wireless PAU09 | RTL8812AU | USB 3.0 | 2.4 + 5 GHz | 80 MHz | ~$35 | Similar to AWUS036ACHM |
| Intel AX200 | PCIe/M.2 | Internal | 2.4 + 5 + 6 GHz | 160 MHz | ~$20 | Wi-Fi 6, tri-band. Needs M.2 slot. |
| Intel AX210 | PCIe/M.2 | Internal | 2.4 + 5 + 6 GHz | 160 MHz | ~$25 | Wi-Fi 6E, tri-band. Best for 6 GHz. |

### Tier 2: Good (Works with Caveats)

| Adapter | Chipset | Notes |
|---------|---------|-------|
| TP-Link TL-WN722N v1 | AR9271 | v1 only! v2/v3 use different chipset (no monitor). |
| TP-Link TL-WN821N v4/v5 | RTL8192EU | Needs rtl8192eu driver. |
| Comfast CF-WU810N | RTL8188EUS | Limited frame capture. Entry level. |
| AWUS036NHA | AR9271 | Good for 2.4 GHz only. |

### Tier 3: Avoid (No/Fake Monitor Mode)

| Adapter | Chipset | Reason |
|---------|---------|--------|
| Raspberry Pi built-in | BCM43455/BCM2712 | brcmfmac driver lacks real monitor mode |
| TP-Link TL-WN722N v2/v3 | QCA9377 | No monitor mode support |
| TP-Link TL-WN823N | RTL8192EU | Unreliable in monitor mode |
| Cheap no-name USB adapters | Various | Often fake monitor mode |
| Most internal laptop Wi-Fi | Various | Whitelist restrictions, no USB |

## Driver Installation

### RTL8812AU / RTL8814AU

```bash
# Install from source (recommended)
git clone https://github.com/morrownr/88x2bu-20210702.git
cd 88x2bu-20210702
sudo ./install-driver.sh

# Or via DKMS (persists across kernel updates)
sudo apt install -y dkms
# Follow the repo's DKMS instructions
```

### RTL8192EU

```bash
git clone https://github.com/Mange/rtl8192eu-linux-driver.git
cd rtl8192eu-linux-driver
sudo dkms install .
```

### Intel AX200/AX210

Built into the kernel (`iwlwifi`). Enable monitor mode:

```bash
# Check if connected (disable it first)
 sudo iw dev wlan0 disconnect
 sudo ip link set wlan0 down
 sudo iw dev wlan0 set type monitor
 sudo ip link set wlan0 up
```

Note: On some Intel chipsets, the firmware may drop packets in monitor mode. This is a known limitation.

## Multiple Adapters (Multi-Band Monitoring)

To monitor 2.4 GHz and 5 GHz simultaneously, you need **two adapters** — one per band. Example:

```bash
# Adapter 1: 2.4 GHz (Alfa AWUS036ACH on wlan1)
sudo ./scripts/setup-monitor-mode.sh wlan1

# Adapter 2: 5 GHz (Alfa AWUS036ACHM on wlan2)
sudo ./scripts/setup-monitor-mode.sh wlan2
```

Then configure Kismet to use both:

```bash
# In kismet_site.conf or via command line
# source=wlan1:type=linuxwifi
# source=wlan2:type=linuxwifi
```

## Checking Adapter Capabilities

Run the included check script:

```bash
sudo ./scripts/check-nic.sh wlan1
```

This will show:
- Driver and chipset
- Current mode
- Supported bands
- Monitor mode support

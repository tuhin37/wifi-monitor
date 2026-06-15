# Supported Wi-Fi Hardware

Monitor mode is required for passive scanning (Kismet/iw).
The management interface can use any standard Wi-Fi adapter.

## Tier 1: Recommended

| Adapter | Chipset | Interface | Bands | Notes |
|---------|---------|-----------|-------|-------|
| Alfa AWUS036ACHM | RTL8812AU | USB 3.0 | 2.4+5 GHz | Best all-rounder |
| Alfa AWUS036ACH | AR9271 | USB 2.0 | 2.4 GHz | Works out of box |
| Panda PAU09 | RTL8812AU | USB 3.0 | 2.4+5 GHz | Good value |
| Intel AX200/AX210 | PCIe/M.2 | Internal | 2.4+5+6 GHz | Wi-Fi 6/6E |

## Tier 2: Works with Drivers

| Adapter | Chipset | Notes |
|---------|---------|-------|
| TP-Link TL-WN722N v1 | AR9271 | v1 only! v2/v3 use different chipset |
| Comfast CF-WU810N | RTL8188EUS | Limited frame capture |
| AWUS036NHA | AR9271 | 2.4 GHz only |

## Tier 3: Avoid

- Raspberry Pi built-in Wi-Fi (brcmfmac) — no real monitor mode
- TP-Link TL-WN722N v2/v3 — QCA9377, no monitor mode
- Most cheap no-name USB adapters

## Driver Install (RTL8812AU)

```bash
git clone https://github.com/morrownr/88x2bu-20210702.git
cd 88x2bu-20210702
sudo ./install-driver.sh
```

## Check Your Adapter

```bash
sudo ./scripts/check-nic.sh wlan1
```

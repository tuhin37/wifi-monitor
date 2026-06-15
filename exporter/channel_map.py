"""
Frequency-to-channel mapping for 2.4 GHz, 5 GHz, and 6 GHz Wi-Fi bands.

Maps center frequency (MHz) to channel number.
Kismet reports frequency in MHz via device['kismet.device.base.frequency'].
"""

# 2.4 GHz band: channels 1-14 (2412-2484 MHz)
FREQ_TO_CHANNEL_2GHZ = {
    2412: 1,  2417: 2,  2422: 3,  2427: 4,
    2432: 5,  2437: 6,  2442: 7,  2447: 8,
    2452: 9,  2457: 10, 2462: 11, 2467: 12,
    2472: 13, 2484: 14,
}

# 5 GHz band: channels 32-177 (5160-5885 MHz)
FREQ_TO_CHANNEL_5GHZ = {
    5160: 32, 5170: 34, 5180: 36, 5190: 38,
    5200: 40, 5210: 42, 5220: 44, 5230: 46,
    5240: 48, 5250: 50, 5260: 52, 5270: 54,
    5280: 56, 5290: 58, 5300: 60, 5310: 62,
    5320: 64, 5340: 68, 5480: 96, 5500: 100,
    5510: 102, 5520: 104, 5530: 106, 5540: 108,
    5550: 110, 5560: 112, 5570: 114, 5580: 116,
    5590: 118, 5600: 120, 5610: 122, 5620: 124,
    5630: 126, 5640: 128, 5660: 132, 5670: 134,
    5680: 136, 5690: 138, 5700: 140, 5710: 142,
    5720: 144, 5745: 149, 5755: 151, 5765: 153,
    5775: 155, 5785: 157, 5795: 159, 5805: 161,
    5815: 163, 5825: 165, 5845: 169, 5865: 173,
    5885: 177,
}

# 6 GHz band (Wi-Fi 6E): channels 1-233 (5955-7115 MHz)
# Each step is 5 MHz, channels are numbered 1, 5, 9, 13, ...
FREQ_TO_CHANNEL_6GHZ = {}
for _ch in range(1, 234, 4):
    _freq = 5955 + (_ch - 1) * 5
    FREQ_TO_CHANNEL_6GHZ[_freq] = _ch


def frequency_to_channel(freq_mhz: int) -> int:
    """Convert frequency in MHz to Wi-Fi channel number.

    Returns 0 if the frequency is not in any known channel mapping.
    """
    if not freq_mhz:
        return 0
    freq_mhz = int(freq_mhz)

    # Round to nearest 5 MHz for matching since Kismet may report
    # center frequency with slight variation or HT40+/HT80 center freqs
    channel = FREQ_TO_CHANNEL_2GHZ.get(freq_mhz)
    if channel:
        return channel

    channel = FREQ_TO_CHANNEL_5GHZ.get(freq_mhz)
    if channel:
        return channel

    channel = FREQ_TO_CHANNEL_6GHZ.get(freq_mhz)
    if channel:
        return channel

    # Try rounding to nearest valid frequency
    if 2400 <= freq_mhz <= 2500:
        nearest = min(FREQ_TO_CHANNEL_2GHZ.keys(), key=lambda x: abs(x - freq_mhz))
        if abs(nearest - freq_mhz) <= 5:
            return FREQ_TO_CHANNEL_2GHZ[nearest]
    elif 5150 <= freq_mhz <= 5900:
        nearest = min(FREQ_TO_CHANNEL_5GHZ.keys(), key=lambda x: abs(x - freq_mhz))
        if abs(nearest - freq_mhz) <= 10:
            return FREQ_TO_CHANNEL_5GHZ[nearest]
    elif 5925 <= freq_mhz <= 7125:
        nearest = min(FREQ_TO_CHANNEL_6GHZ.keys(), key=lambda x: abs(x - freq_mhz))
        if abs(nearest - freq_mhz) <= 10:
            return FREQ_TO_CHANNEL_6GHZ[nearest]

    return 0


def frequency_to_band(freq_mhz: int) -> str:
    """Return band label for a frequency in MHz."""
    if not freq_mhz:
        return "unknown"
    freq_mhz = int(freq_mhz)
    if 2400 <= freq_mhz <= 2500:
        return "2.4 GHz"
    elif 5150 <= freq_mhz <= 5900:
        return "5 GHz"
    elif 5925 <= freq_mhz <= 7125:
        return "6 GHz"
    return "unknown"


def estimate_channel_width(freq_mhz: int, ht_cap: dict = None, vht_cap: dict = None) -> int:
    """Estimate channel width in MHz based on frequency and capabilities.

    Actually determining channel width requires looking at the beacon frame
    HT/VHT/HE information elements. Kismet may not always expose this.
    This is a best-effort estimator.
    """
    if ht_cap or vht_cap:
        # If we had capability data we could infer width
        pass
    # Without beacon data, we can't determine width from frequency alone
    return 0

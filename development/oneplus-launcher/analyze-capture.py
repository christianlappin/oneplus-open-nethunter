"""Summarize saved 802.11 captures without transmitting or modifying them."""
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

FIELDS = (
    "wlan.fc.type", "wlan.fc.type_subtype", "wlan.bssid", "wlan.ssid",
    "radiotap.channel.freq", "radiotap.dbm_antsignal", "wlan.ds.current_channel",
    "wlan.ht.info.primarychannel", "wlan.fixed.capabilities.privacy",
    "wlan.rsn.version", "wlan.rsn.akms.oui", "wlan.rsn.akms.type", "wlan.wfa.ie.wpa.akms.type",
    "wlan.rsn.capabilities.mfpc", "wlan.rsn.capabilities.mfpr", "eapol.version",
)
AKM = {
    "1": "802.1X", "2": "PSK", "3": "FT/802.1X", "4": "FT/PSK",
    "5": "802.1X-SHA256", "6": "PSK-SHA256", "8": "SAE", "9": "FT/SAE",
    "11": "802.1X Suite B", "12": "802.1X Suite B 192-bit",
    "13": "FT/802.1X-SHA384", "18": "OWE",
    "24": "SAE Extended Key", "25": "FT/SAE Extended Key",
}


def first(value):
    return value.split(",", 1)[0]


def ssid(value):
    try:
        decoded = bytes.fromhex(first(value)).decode("utf-8", errors="replace")
    except ValueError:
        return "(unreadable SSID)"
    if not decoded.strip("\0 "):
        return "(hidden SSID)"
    return "".join(c if unicodedata.category(c)[0] != "C" else "�" for c in decoded)[:32]


def flag(value):
    return {"true": True, "1": True, "false": False, "0": False}.get(first(value).lower())


def describe_security(rsn, ouis, akms, wpa, privacy, capable, required):
    suites = []
    standard = set()
    for oui, suite in zip(ouis.split(","), akms.split(",")):
        if not suite:
            continue
        if oui.lower() in {"0x000fac", "00:0f:ac", "4012"}:
            standard.add(suite)
            suites.append(AKM.get(suite, f"AKM {suite}"))
        else:
            suites.append(f"AKM {oui or '?'}/{suite}")

    sae = bool(standard & {"8", "9", "24", "25"})
    psk = bool(standard & {"2", "4", "6"})
    advertised = []
    if sae and psk:
        advertised.append("WPA2/WPA3-Personal transition")
    elif sae:
        advertised.append("WPA3-Personal (SAE)")
    elif psk:
        advertised.append("WPA2-Personal (PSK)")
    if "18" in standard:
        advertised.append("Enhanced Open (OWE)")
    if standard & {"1", "3", "5", "11", "12", "13"}:
        advertised.append("Enterprise (802.1X)")
    if wpa:
        advertised.append("legacy WPA")
    if not advertised:
        if rsn:
            advertised.append("RSN security (mode undetermined)")
        elif privacy is True:
            advertised.append("Privacy set; no decoded WPA/RSN")
        elif privacy is False:
            advertised.append("Open")
        else:
            advertised.append("Unknown")

    if capable is True and required is True:
        pmf = "Required"
    elif capable is True and required is False:
        pmf = "Optional (capable)"
    elif capable is False and required is False:
        pmf = "Disabled"
    elif capable is False and required is True:
        pmf = "Inconsistent flags"
    elif not rsn and privacy is not None:
        pmf = "Not advertised (no RSN)"
    else:
        pmf = "Unknown (RSN capabilities missing)"
    return " + ".join(advertised), ", ".join(dict.fromkeys(suites)), pmf


def describe(row):
    (_, _, _, raw_name, freq, signal, ds, ht, privacy, rsn, ouis, akms,
     wpa, capable, required, _) = row
    channel = first(ds or ht)
    frequency = first(freq)
    if not channel and frequency.isdecimal():
        n = int(frequency)
        if n == 2484:
            channel = "14"
        elif 2412 <= n <= 2472:
            channel = str((n - 2407) // 5)
        elif 5000 < n < 5925:
            channel = str((n - 5000) // 5)
        elif n == 5935:
            channel = "2"
        elif 5955 <= n <= 7115 and (n - 5950) % 5 == 0:
            channel = str((n - 5950) // 5)
    security = describe_security(first(rsn),
                                 ouis, akms, wpa, flag(privacy), flag(capable), flag(required))
    return ssid(raw_name), channel or "?", frequency, first(signal), security


def summarize(path):
    counts = Counter()
    access_points = {}
    cmd = ["tshark", "-n", "-r", str(path), "-T", "fields"]
    for field in FIELDS:
        cmd += ["-e", field]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as process:
        for line in process.stdout:
            row = line.rstrip("\n").split("\t")
            if len(row) != len(FIELDS):
                continue
            counts["all"] += 1
            counts[first(row[0])] += 1
            if row[-1]:
                counts["eapol"] += 1
            if (first(row[1]) in {"0x0008", "0x0005"}
                    and re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", row[2])):
                bssid = row[2]
                if bssid not in access_points and len(access_points) >= 512:
                    continue
                previous, count = access_points.get(bssid, (None, 0))
                details = describe(row)
                if previous and details[0] == "(hidden SSID)":
                    details = (previous[0], *details[1:])
                access_points[bssid] = (details, count + 1)
        if process.wait():
            raise ValueError("TShark could not read this capture.")
    print(f"{path.name}\n")
    print(f"{counts['all']} frames · {counts['0']} management · {counts['1']} control · {counts['2']} data")
    print(f"EAPOL frames: {counts['eapol']} (does not establish handshake completeness)")
    print(f"Access points with a beacon or probe response: {len(access_points)}"
          + (" or more" if len(access_points) == 512 else ""))
    for bssid, (details, _) in sorted(access_points.items(), key=lambda entry: -entry[1][1])[:40]:
        name, channel, frequency, signal, (security, suites, pmf) = details
        print(f"\n{name} · {bssid}\nChannel {channel}"
              + (f" · {frequency} MHz" if frequency else "")
              + (f" · {signal} dBm (last seen)" if signal else ""))
        print(f"Advertised security: {security}")
        if suites:
            print(f"RSN authentication suites: {suites}")
        print(f"Protected management frames (PMF): {pmf}")
    if len(access_points) > 40:
        print("\nShowing the 40 most observed access points. Open the PCAP for the full list.")


if __name__ == "__main__":
    try:
        capture = Path(sys.argv[1])
        if capture.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("This capture exceeds the phone summary limit (128 MiB). Open it in Wireshark.")
        summarize(capture)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)

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
    "wlan.rsn.akms.oui", "wlan.rsn.akms.type", "wlan.wfa.ie.wpa.akms.type",
    "wlan.rsn.capabilities.mfpc", "wlan.rsn.capabilities.mfpr", "eapol.version",
)
AKM = {
    "1": "802.1X", "2": "PSK", "3": "FT/802.1X", "4": "FT/PSK",
    "5": "802.1X-SHA256", "6": "PSK-SHA256", "8": "SAE", "9": "FT/SAE",
    "11": "802.1X Suite B", "12": "802.1X Suite B 192-bit",
    "13": "FT/802.1X-SHA384", "18": "OWE",
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


def describe(row):
    _, _, _, raw_name, freq, signal, ds, ht, privacy, ouis, akms, wpa, capable, required, _ = row
    channel = first(ds or ht)
    frequency = first(freq)
    if not channel and frequency.isdecimal():
        n = int(frequency)
        if 2412 <= n <= 2472:
            channel = str((n - 2407) // 5)
        elif 5000 < n < 5925:
            channel = str((n - 5000) // 5)
    advertised = []
    if akms:
        suites = []
        for oui, suite in zip(ouis.split(","), akms.split(",")):
            known_oui = oui.lower() in {"0x000fac", "00:0f:ac", "4012"}
            suites.append(AKM.get(suite, f"AKM {suite}") if known_oui else f"AKM {oui}/{suite}")
        advertised.append("RSN (" + ", ".join(dict.fromkeys(suites or [akms])) + ")")
    if wpa:
        advertised.append("legacy WPA")
    if not advertised:
        advertised.append("privacy set; no decoded WPA/RSN" if privacy == "1" else
                          "open (advertised)" if privacy == "0" else "unknown")
    pmf = ("required" if required == "1" else "capable, not required" if capable == "1"
           else "not advertised" if capable == "0" else "unknown")
    signal = first(signal)
    return ssid(raw_name), channel or "?", frequency, signal, " + ".join(advertised), pmf


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
        name, channel, frequency, signal, security, pmf = details
        print(f"\n{name} · {bssid}\nChannel {channel}"
              + (f" · {frequency} MHz" if frequency else "")
              + (f" · {signal} dBm (last seen)" if signal else ""))
        print(f"Advertised: {security}\nProtected management frames: {pmf}")
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

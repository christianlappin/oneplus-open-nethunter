#!/usr/bin/env python3
"""Read short radiotap PCAPs from the launcher and report their beacons."""

from pathlib import Path
import struct
import sys


def packets(path):
    with path.open("rb") as capture:
        header = capture.read(24)
        byte_order = {b"\xd4\xc3\xb2\xa1": "<", b"\x4d\x3c\xb2\xa1": "<",
                      b"\xa1\xb2\xc3\xd4": ">", b"\xa1\xb2\x3c\x4d": ">"}.get(header[:4])
        if not byte_order or len(header) != 24:
            return
        if struct.unpack_from(byte_order + "I", header, 20)[0] & 0xFFFF != 127:
            return
        while len(record := capture.read(16)) == 16:
            length = struct.unpack_from(byte_order + "I", record, 8)[0]
            if length > 262144:
                return
            packet = capture.read(length)
            if len(packet) != length:
                return
            yield packet


def radio_frequency(packet, end):
    offset = 4
    if end < 8:
        return None
    first = struct.unpack_from("<I", packet, offset)[0]
    present = first
    while present & (1 << 31):
        offset += 4
        if offset + 4 > end:
            return None
        present = struct.unpack_from("<I", packet, offset)[0]
    offset += 4
    if not first & 8:
        return None
    for bit, size in ((0, 8), (1, 1), (2, 1), (3, 4)):
        if not first & (1 << bit):
            continue
        alignment = 8 if bit == 0 else 2 if bit == 3 else 1
        offset = (offset + alignment - 1) & ~(alignment - 1)
        if offset + size > end:
            return None
        if bit == 3:
            return struct.unpack_from("<H", packet, offset)[0]
        offset += size
    return None


def beacon(packet, frequency):
    if len(packet) < 8 or packet[0] != 0:
        return None
    end = struct.unpack_from("<H", packet, 2)[0]
    if end < 8 or len(packet) < end + 36 or packet[end] != 0x80:
        return None
    received = radio_frequency(packet, end)
    if received and received != frequency:
        return None

    channel = (frequency - (2407 if frequency < 2500 else 5000)) // 5
    fields = {}
    offset = end + 36
    while offset + 2 <= len(packet):
        tag, length = packet[offset:offset + 2]
        offset += 2
        if offset + length > len(packet):
            break
        fields.setdefault(tag, packet[offset:offset + length])
        offset += length

    primary = fields.get(3) or fields.get(61)
    if primary and primary[0] != channel:
        return None
    if not received and not primary:
        return None
    if 0 not in fields:
        return None
    raw_name = fields[0]
    name = raw_name.decode("utf-8", errors="replace")
    name = "".join(char if char.isprintable() else " " for char in name).strip()
    address = ":".join(f"{value:02x}" for value in packet[end + 16:end + 22])
    return address, name or "Hidden network"


def main(directory):
    networks = {}
    for path in directory.glob("*.pcap"):
        frequency = int(path.stem)
        for packet in packets(path):
            result = beacon(packet, frequency)
            if result:
                address, name = result
                networks[frequency, address] = name
    for (frequency, address), name in sorted(networks.items(), key=lambda item: (item[0][0], item[1].casefold())):
        print(f"NH-AP {frequency}\t{address}\t{name}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

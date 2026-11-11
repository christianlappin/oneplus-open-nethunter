#!/usr/bin/env python3
"""Read stock split BTF to record cfg80211 interface structure layouts."""
import json
import struct
from pathlib import Path


def elf_section(path, wanted):
    data = Path(path).read_bytes()
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 58)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size)
               for i in range(count)]
    h = headers[names_index]
    strings = data[h[4]:h[4] + h[5]]
    for h in headers:
        name = strings[h[0]:strings.index(b'\0', h[0])].decode()
        if name == wanted:
            return data[h[4]:h[4] + h[5]]
    raise ValueError(wanted)


def read_btf(data, base_strings=b'', first_id=1):
    magic, version, flags, hdrlen, toff, tlen, soff, slen = struct.unpack_from('<HBBIIIII', data)
    assert magic == 0xeb9f and version == 1
    local = data[hdrlen + soff:hdrlen + soff + slen]
    strings = base_strings + local
    def name(off):
        return strings[off:strings.index(b'\0', off)].decode()
    pos, end = hdrlen + toff, hdrlen + toff + tlen
    types = []
    while pos < end:
        noff, info, length = struct.unpack_from('<III', data, pos)
        kind, vlen = (info >> 24) & 31, info & 65535
        pos += 12
        extra = {1: 4, 2: 0, 3: 12, 4: vlen * 12, 5: vlen * 12,
                 6: vlen * 8, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0,
                 12: 0, 13: vlen * 8, 14: 4, 15: vlen * 12,
                 16: 0, 17: 4, 18: 0, 19: vlen * 12}[kind]
        record = {'id': first_id + len(types), 'kind': kind, 'name': name(noff), 'size_or_type': length}
        if kind in (4, 5):
            members = []
            for i in range(vlen):
                moff, typ, bitoff = struct.unpack_from('<III', data, pos + i * 12)
                members.append({'name': name(moff), 'type': typ,
                                'bit_offset': bitoff & 0xffffff if info >> 31 else bitoff,
                                'bitfield_size': bitoff >> 24 if info >> 31 else 0})
            record['members'] = members
        types.append(record)
        pos += extra
    assert pos == end
    return types, strings


root = Path(__file__).resolve().parent.parent
base, strings = read_btf((root / 'research/kernel-audit/stock-build/vmlinux.btf').read_bytes())
module, _ = read_btf(elf_section(root / 'research/kernel-audit/stock-build/vendor-modules/cfg80211.ko', '.BTF'),
                     strings, len(base) + 1)
selected = [t for t in base + module if t['name'] in ('wiphy', 'cfg80211_ops', 'wireless_dev') and t['kind'] == 4]
print(json.dumps(selected, indent=2))

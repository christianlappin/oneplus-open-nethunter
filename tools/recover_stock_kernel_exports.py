#!/usr/bin/env python3
"""Recover core-kernel exports/CRCs from an ELF reconstructed from stock Image.

Reject a bad address mapping or CRC mismatch against installed WLAN imports.
This is recovered evidence, not an OEM-generated complete Module.symvers.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
directory = ROOT / 'research/kernel-audit/stock-build'
blob = (directory / 'vmlinux.recovered.elf').read_bytes()
assert blob[:6] == b'\x7fELF\x02\x01'
offset = struct.unpack_from('<Q', blob, 40)[0]
size, count, names_index = struct.unpack_from('<HHH', blob, 58)
headers = [struct.unpack_from('<IIQQQQIIQQ', blob, offset + i * size)
           for i in range(count)]


def section_data(h):
    return blob[h[4]:h[4] + h[5]]


names = section_data(headers[names_index])
sections = {names[h[0]:].split(b'\0', 1)[0].decode(): h for h in headers}
symtab = sections['.symtab']
strings = section_data(headers[symtab[6]])
symbols = {}
for i in range(symtab[4], symtab[4] + symtab[5], symtab[9]):
    name, info, other, index, value, length = struct.unpack_from('<IBBHQQ', blob, i)
    name = strings[name:strings.index(b'\0', name)].decode()
    if name:
        symbols[name] = value


def read(address, length):
    for h in headers:
        if h[1] != 8 and h[2] & 2 and h[3] <= address and address + length <= h[3] + h[5]:
            i = h[4] + address - h[3]
            return blob[i:i + length]
    raise ValueError(f'address is not file-backed: {address:x}')


def cstring(address):
    # Namespaces and symbol names are bounded; require a terminating NUL.
    value = read(address, 256).split(b'\0', 1)
    assert len(value) == 2
    return value[0].decode('ascii')


exports = {}
for suffix, export_type in [('', 'EXPORT_SYMBOL'), ('_gpl', 'EXPORT_SYMBOL_GPL')]:
    start, stop = (symbols['__' + end + '___ksymtab' + suffix] for end in ('start', 'stop'))
    crc_start, crc_stop = (symbols['__' + end + '___kcrctab' + suffix] for end in ('start', 'stop'))
    assert (stop - start) % 12 == 0
    n = (stop - start) // 12
    assert crc_stop - crc_start == n * 4
    for i in range(n):
        address = start + i * 12
        value_delta, name_delta, namespace_delta = struct.unpack('<iii', read(address, 12))
        name = cstring(address + 4 + name_delta)
        namespace = cstring(address + 8 + namespace_delta)
        assert name and name not in exports
        crc = struct.unpack('<I', read(crc_start + i * 4, 4))[0]
        exports[name] = {'crc': f'{crc:08x}', 'namespace': namespace, 'type': export_type}

stock = json.loads((ROOT / 'research/kernel-audit/kiwi-stock-abi.json').read_text())
crcs = stock['imported_symbol_crcs']
matched = [n for n in crcs if n in exports and crcs[n] == exports[n]['crc']]
mismatched = [n for n in crcs if n in exports and crcs[n] != exports[n]['crc']]
assert len(matched) > 100 and not mismatched, (len(matched), mismatched)
# Kbuild order is CRC, symbol, module, export type, namespace.
lines = [f"0x{e['crc']}\t{name}\tvmlinux\t{e['type']}\t{e['namespace']}"
         for name, e in sorted(exports.items())]
(directory / 'Module.symvers.core.recovered').write_text('\n'.join(lines) + '\n')
report = {'origin': 'verified stock boot Image; reconstructed ELF, not OEM ELF',
          'image_sha256': hashlib.sha256((directory / 'Image').read_bytes()).hexdigest(),
          'export_count': len(exports), 'wlan_core_imports_matched': len(matched),
          'crc_mismatches': mismatched,
          'wlan_imports_not_in_core': sorted(set(crcs) - set(exports)),
          'exports': exports}
(directory / 'kernel-exports-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('Recovered core exports:', len(exports))
print('Independently matched installed WLAN symbol CRCs:', len(matched))
print('WLAN imports from vendor modules:', len(set(crcs) - set(exports)))

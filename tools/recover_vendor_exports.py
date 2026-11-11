#!/usr/bin/env python3
"""Recover signed-stock vendor export CRCs and check all saved WLAN imports."""
import json
import hashlib
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'research/kernel-audit/stock-build'
core = json.loads((OUT / 'kernel-exports-verification.json').read_text())
all_exports = {name: dict(value, owner='vmlinux') for name, value in core['exports'].items()}
providers = {}
provider_hashes = {}
for path in sorted((OUT / 'vendor-modules').glob('*.ko')):
    data = path.read_bytes()
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 58)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size) for i in range(count)]

    def section(h):
        return data[h[4]:h[4] + h[5]]

    names = section(headers[names_index])
    section_names = [names[h[0]:names.index(b'\0', h[0])].decode() for h in headers]
    symtab = headers[section_names.index('.symtab')]
    strings = section(headers[symtab[6]])
    symbols = {}
    for i in range(symtab[4], symtab[4] + symtab[5], symtab[9]):
        name, info, other, index, value, length = struct.unpack_from('<IBBHQQ', data, i)
        name = strings[name:strings.index(b'\0', name)].decode()
        symbols[name] = (index, value)
    exports = {}
    for symbol, (index, value) in symbols.items():
        if not symbol.startswith('__crc_'):
            continue
        assert index == 0xfff1 and value <= 0xffffffff, (path, symbol, index)
        name = symbol[6:]
        table_index, _ = symbols['__ksymtab_' + name]
        export_type = 'EXPORT_SYMBOL_GPL' if 'gpl' in section_names[table_index] else 'EXPORT_SYMBOL'
        string_index, namespace_offset = symbols['__kstrtabns_' + name]
        text = section(headers[string_index])
        namespace = text[namespace_offset:text.index(b'\0', namespace_offset)].decode()
        exports[name] = {'crc': f'{value:08x}', 'namespace': namespace,
                         'type': export_type, 'owner': path.stem}
    for name, record in exports.items():
        assert name not in all_exports or all_exports[name] == record, name
        all_exports[name] = record
    providers[path.name] = len(exports)
    provider_hashes[path.name] = hashlib.sha256(data).hexdigest()

expected = json.loads((ROOT / 'research/kernel-audit/kiwi-stock-abi.json').read_text())['imported_symbol_crcs']
missing = sorted(set(expected) - set(all_exports))
mismatches = [n for n, crc in expected.items() if n in all_exports and crc != all_exports[n]['crc']]
report = {'provider_export_counts': providers, 'total_exports': len(all_exports),
          'provider_sha256': provider_hashes,
          'required_wlan_symbols': len(expected), 'verified': len(expected) - len(missing) - len(mismatches),
          'missing': missing, 'mismatches': mismatches}
(OUT / 'vendor-exports-verification.json').write_text(json.dumps(report, indent=2) + '\n')
assert not mismatches, mismatches
print(json.dumps(report, indent=2))
if not missing:
    lines = [f"0x{e['crc']}\t{n}\t{e['owner']}\t{e['type']}\t{e['namespace']}"
             for n, e in sorted(all_exports.items())]
    (OUT / 'Module.symvers.recovered').write_text('\n'.join(lines) + '\n')
    print('Wrote recovered symbol input; all 525 installed WLAN imports independently matched')

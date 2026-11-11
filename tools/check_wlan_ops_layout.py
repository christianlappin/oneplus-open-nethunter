#!/usr/bin/env python3
"""Compare populated cfg80211 callback offsets without loading either ELF."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def callbacks(path, symbol_name='wlan_hdd_cfg80211_ops'):
    data = Path(path).read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01'
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 58)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size)
               for i in range(count)]
    def section(h):
        return data[h[4]:h[4] + h[5]]
    def string(table, i):
        return table[i:table.index(b'\0', i)].decode()
    names = section(headers[names_index])
    symtab = next(h for h in headers if string(names, h[0]) == '.symtab')
    strings = section(headers[symtab[6]])
    symbols = []
    for i in range(symtab[4], symtab[4] + symtab[5], 24):
        name, info, other, shndx, value, length = struct.unpack_from('<IBBHQQ', data, i)
        symbols.append((string(strings, name), shndx, value, length))
    ops = next(s for s in symbols if s[0] == symbol_name)
    by_address = {(s[1], s[2]): s[0] for s in symbols
                  if s[0] and not s[0].startswith('$')}
    populated = {}
    for h in headers:
        if h[1] != 4 or h[7] != ops[1]:
            continue
        for i in range(h[4], h[4] + h[5], 24):
            address, info, addend = struct.unpack_from('<QQq', data, i)
            if ops[2] <= address < ops[2] + ops[3]:
                symbol = symbols[info >> 32]
                target = by_address.get((symbol[1], symbol[2] + addend),
                                        symbol[0] or f'section{symbol[1]}+{addend}')
                target = target.removesuffix('.cfi_jt')
                populated[target] = address - ops[2]
    return {'bytes': ops[3], 'callbacks': populated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock')
    parser.add_argument('candidate')
    args = parser.parse_args()
    stock, candidate = callbacks(args.stock), callbacks(args.candidate)
    shared = stock['callbacks'].keys() & candidate['callbacks'].keys()
    mismatch = {name: {'stock': stock['callbacks'][name], 'candidate': candidate['callbacks'][name]}
                for name in sorted(shared) if stock['callbacks'][name] != candidate['callbacks'][name]}
    result = {'stock_bytes': stock['bytes'], 'candidate_bytes': candidate['bytes'],
              'stock_sha256': hashlib.sha256(Path(args.stock).read_bytes()).hexdigest(),
              'candidate_sha256': hashlib.sha256(Path(args.candidate).read_bytes()).hexdigest(),
              'shared_callbacks': len(shared), 'offset_mismatches': mismatch,
              'missing': sorted(stock['callbacks'].keys() - candidate['callbacks'].keys()),
              'additional': sorted(candidate['callbacks'].keys() - stock['callbacks'].keys()),
              'stock': stock, 'candidate': candidate}
    print(json.dumps(result, indent=2))
    return bool(mismatch or stock['bytes'] != candidate['bytes'] or
                result['missing'] or result['additional'])


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Conservative preflight for a replacement of the saved KIWI_V2 module.

Read ELF directly, without loading it. Matching this gate does not prove safe
execution, CFI compatibility, signature acceptance, or RF behavior.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def inspect(path):
    data = Path(path).read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected ELF64 little-endian')
    if struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('expected AArch64 module')
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 58)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size)
               for i in range(count)]
    names = headers[names_index]
    strings = data[names[4]:names[4] + names[5]]
    sections = {}
    section_headers = {}
    for h in headers:
        name = strings[h[0]:].split(b'\0', 1)[0].decode()
        sections[name] = data[h[4]:h[4] + h[5]]
        section_headers[name] = h
    info = {}
    for item in sections['.modinfo'].split(b'\0'):
        if b'=' in item:
            key, value = item.decode().split('=', 1)
            info.setdefault(key, []).append(value)
    versions = sections['__versions']
    if len(versions) % 64:
        raise ValueError('unexpected modversion entry size')
    crcs = {}
    for i in range(0, len(versions), 64):
        crc = struct.unpack_from('<Q', versions, i)[0]
        name = versions[i + 8:i + 64].split(b'\0', 1)[0].decode()
        crcs[name] = f'{crc:08x}'
    symtab = section_headers['.symtab']
    if symtab[9] != 24:
        raise ValueError('unexpected ELF64 symbol entry size')
    string_header = headers[symtab[6]]
    symbol_strings = data[string_header[4]:string_header[4] + string_header[5]]
    undefined = {'strong': [], 'weak': []}
    for offset in range(symtab[4], symtab[4] + symtab[5], 24):
        name, symbol_info, _, index, _, _ = struct.unpack_from('<IBBHQQ', data, offset)
        binding = symbol_info >> 4
        if index == 0 and name and binding in (1, 2):
            symbol = symbol_strings[name:].split(b'\0', 1)[0].decode()
            undefined['weak' if binding == 2 else 'strong'].append(symbol)
    return {'sha256': hashlib.sha256(data).hexdigest(), 'modinfo': info,
            'imported_symbol_crcs': crcs,
            'undefined_symbols': {k: sorted(v) for k, v in undefined.items()},
            'cfi_sections': sorted(n for n in sections if 'cfi' in n.lower())}


def compare(stock, candidate, exports=None, kernel_release=None):
    errors = []
    for key in ('name',):
        if stock['modinfo'].get(key) != candidate['modinfo'].get(key):
            errors.append(f'{key} differs')
    if kernel_release:
        # The stock kernel's same_magic() ignores the release prefix for
        # versioned modules. Require the candidate to name the actual target
        # kernel, preserve the ABI flags, and validate CRCs independently.
        original = stock['modinfo']['vermagic'][0].split(' ', 1)
        proposed = candidate['modinfo']['vermagic'][0].split(' ', 1)
        if proposed[0] != kernel_release or original[1:] != proposed[1:]:
            errors.append('target kernel release or vermagic ABI flags differ')
        if not exports or not candidate['imported_symbol_crcs']:
            errors.append('target-release validation requires independent export CRCs')
    elif stock['modinfo'].get('vermagic') != candidate['modinfo'].get('vermagic'):
        errors.append('vermagic differs')
    if stock['cfi_sections'] != candidate['cfi_sections']:
        errors.append('CFI section layout differs; review the toolchain/config')
    expected = stock['imported_symbol_crcs']
    for symbol in candidate['undefined_symbols']['strong']:
        if symbol not in candidate['imported_symbol_crcs']:
            errors.append(f'undefined symbol has no module-version CRC: {symbol}')
    for symbol, crc in candidate['imported_symbol_crcs'].items():
        if exports is not None:
            if symbol not in exports:
                errors.append(f'import absent from verified stock exports: {symbol}')
            elif exports[symbol] != crc:
                errors.append(f'provider symbol CRC mismatch: {symbol}')
        if symbol not in expected and exports is None:
            errors.append(f'new import needs independent kernel ABI verification: {symbol}')
        elif symbol in expected and expected[symbol] != crc:
            errors.append(f'symbol CRC mismatch: {symbol}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock')
    parser.add_argument('candidate', nargs='?')
    parser.add_argument('--symvers', help='independently recovered stock export CRC map')
    parser.add_argument('--kernel-release', help='actual target kernel release; requires --symvers')
    args = parser.parse_args()
    stock = inspect(args.stock)
    if args.kernel_release and not args.symvers:
        parser.error('--kernel-release requires --symvers')
    if args.candidate:
        candidate = inspect(args.candidate)
        exports = None
        if args.symvers:
            exports = {}
            for line in Path(args.symvers).read_text().splitlines():
                crc, name, *_ = line.split()
                if name in exports and exports[name] != f'{int(crc, 16):08x}':
                    raise ValueError(f'conflicting export CRC for {name}')
                exports[name] = f'{int(crc, 16):08x}'
        errors = compare(stock, candidate, exports, args.kernel_release)
        print(json.dumps({'preflight_passed': not errors, 'errors': errors,
                          'candidate': candidate}, indent=2))
        return bool(errors)
    print(json.dumps(stock, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

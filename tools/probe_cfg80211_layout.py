#!/usr/bin/env python3
"""Compile structure-offset constants using the actual vendor compile flags.

Run inside the stock builder. Compare these constants against the stock
cfg80211 module's own split BTF rather than the generic core kernel config.
"""
import json
import re
import shlex
import subprocess
from pathlib import Path

root = Path('/work')
driver = root / 'sources/oneplus-sm8550-modules/vendor/qcom/opensource/wlan/qcacld-3.0'
out = root / 'build/cfg80211-layout-probe'
out.mkdir(exist_ok=True)
records = json.loads((root / 'research/kernel-audit/stock-build/cfg80211-stock-struct-layout.json').read_text())
checks = []
for record in records:
    name = record['name']
    checks.append((f'sizeof({name})', f'sizeof(struct {name})', record['size_or_type']))
    for member in record['members']:
        field = member['name']
        if not member['bitfield_size'] and re.fullmatch(r'[a-zA-Z_]\w*', field):
            assert member['bit_offset'] % 8 == 0
            checks.append((f'{name}.{field}', f'__builtin_offsetof(struct {name}, {field})', member['bit_offset'] // 8))
source = out / 'layout.c'
source.write_text('#include <net/cfg80211.h>\nconst unsigned int nh_cfg80211_layout[] __used = {\n' +
                  ',\n'.join(value for _, value, _ in checks) + '\n};\n')
line = (driver / 'core/hdd/src/.wlan_hdd_p2p.o.cmd').read_text().splitlines()[0].split(' := ', 1)[1]
lexer = shlex.shlex(line, posix=True, punctuation_chars=';&|')
lexer.whitespace_split = True
args = []
for token in lexer:
    if token in (';', '&&', '||', '|'):
        break
    args.append(token)
args[0] = str(root / 'tools/toolchains/clang-r450784e/bin/clang')
for i, arg in enumerate(args):
    if arg.startswith('-Wp,-MMD,'):
        args[i] = '-Wp,-MMD,' + str(out / 'layout.d')
    elif arg.endswith('/wlan_hdd_p2p.c'):
        args[i] = str(source)
    elif i and args[i - 1] == '-o':
        args[i] = str(out / 'layout.o')
subprocess.run(args, cwd=root / 'build/stock-module-env/kernel', check=True)
ir = subprocess.check_output([str(root / 'tools/toolchains/clang-r450784e/bin/llvm-dis'),
                              '-o', '-', str(out / 'layout.o')], text=True)
line = next(line for line in ir.splitlines() if line.startswith('@nh_cfg80211_layout ='))
values = [int(x) for x in re.findall(r'i32 (\d+)', line)]
assert len(values) == len(checks), (len(values), len(checks))
comparison = [{'field': label, 'stock': expected, 'candidate': actual}
              for (label, _, expected), actual in zip(checks, values)]
mismatch = [item for item in comparison if item['stock'] != item['candidate']]
report = {'passed': not mismatch, 'checked_fields': len(checks), 'mismatches': mismatch, 'comparison': comparison}
(root / 'research/kernel-audit/stock-build/cfg80211-layout-probe.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['passed', 'checked_fields', 'mismatches']}, indent=2))
raise SystemExit(bool(mismatch))

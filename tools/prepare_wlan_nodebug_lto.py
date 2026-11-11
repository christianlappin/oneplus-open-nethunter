#!/usr/bin/env python3
"""Prepare copied full-LTO inputs with only debug metadata removed.

Run in the linker container. The Android compiler, optimization level, CFI
metadata and source objects are retained. No module is loaded or installed.
"""
import concurrent.futures
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path('/work')
driver = ROOT / 'sources/oneplus-sm8550-modules/vendor/qcom/opensource/wlan/qcacld-3.0'
out = ROOT / 'build/wlan-nodebug-lto'
out.mkdir(exist_ok=True)
objects = [Path(p) for p in (driver / 'kiwi_v2.mod').read_text().split()]
assert 500 < len(objects) < 2000 and len(set(objects)) == len(objects)


def prepare(pair):
    index, source = pair
    target = out / f'{index:04d}.o'
    data = source.read_bytes()
    if data[:4] == b'BC\xc0\xde':
        subprocess.run([str(ROOT / 'build/native/strip_llvm_debug'), str(source), str(target)], check=True)
    else:
        assert data[:4] == b'\x7fELF', source
        shutil.copy2(source, target)
    return {'source': str(source), 'source_sha256': hashlib.sha256(data).hexdigest(),
            'copy': str(target), 'copy_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(prepare, enumerate(objects)))


def cfi_types(path):
    text = subprocess.check_output([str(ROOT / 'tools/toolchains/clang-r450784e/bin/llvm-dis'), '-o', '-', str(path)], text=True)
    records = dict(re.findall(r'^!(\d+) = (.*)$', text, re.M))
    types = sorted(records[n] for n in re.findall(r'!type !(\d+)', text))
    return types, '!llvm.dbg.cu' in text


sample = next(r for r in records if r['source'].endswith('/wlan_hdd_p2p.o'))
before, had_debug = cfi_types(sample['source'])
after, has_debug = cfi_types(sample['copy'])
assert before and before == after and had_debug and not has_debug
archive = out / 'kiwi_v2.nodebug.a'
if archive.exists():
    archive.unlink()
response = out / 'objects.rsp'
response.write_text('\n'.join(r['copy'] for r in records) + '\n')
subprocess.run([str(ROOT / 'tools/toolchains/clang-r450784e/bin/llvm-ar'),
                'rcT', str(archive), '@' + str(response)], check=True)
report = {'copied_inputs': records, 'debug_only_transform': 'Exact Android LLVM8508608 LLVMStripModuleDebugInfo; full IR verifier before/after',
          'cfi_metadata_sample': {'object': sample['source'], 'type_attachments': len(before),
                                  'identical_types': True, 'debug_removed': True},
          'original_objects_modified': False, 'archive': str(archive)}
(out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
print('Prepared', len(records), 'debug-free input copies; CFI metadata sample identical')

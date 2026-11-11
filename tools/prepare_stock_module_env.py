#!/usr/bin/env python3
"""Assemble a host-only external-module environment; never touches the phone.

Use recovered generated headers, the saved configuration, and the pinned
OnePlus build scripts. This is a reconstruction, not OEM build output.
"""
from pathlib import Path
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent
source = ROOT / 'sources/oneplus-sm8550-common'
stock = ROOT / 'research/kernel-audit/stock-build/headers'
dest = ROOT / 'build/stock-module-env/kernel'
if dest.exists():
    shutil.rmtree(dest)  # Only the generated reconstruction, never OEM images.
dest.mkdir(parents=True, exist_ok=True)
for name in ('Makefile', 'Kbuild'):
    shutil.copy2(source / name, dest / name)
for name in ('scripts', 'include', 'arch/arm64', 'net/wireless'):
    shutil.copytree(source / name, dest / name, dirs_exist_ok=True, symlinks=True)

# kheaders strips comments. Keep source comments on semantically matching
# headers, since Qualcomm's Kbuild also probes comments for backport features.
comparison = json.loads((stock.parent / 'header-source-comparison.json').read_text())
for name in comparison['different'] + comparison['absent']:
    path = stock / name
    if path.is_file():
        (dest / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest / name)
# OnePlus's vendor build installs these alongside the core headers.
oplus_headers = ROOT / 'sources/oneplus-sm8550-modules/vendor/oplus/kernel/boot/include'
shutil.copytree(oplus_headers, dest / 'include/soc/oplus/boot', dirs_exist_ok=True, symlinks=True)
config = (ROOT / 'research/kernel-audit/stock.config').read_text()
(dest / '.config').write_text(config)
(dest / 'include/config').mkdir(exist_ok=True)
(dest / 'include/config/auto.conf').write_text('\n'.join(
    line for line in config.splitlines() if line.startswith('CONFIG_')) + '\n')
(dest / 'include/config/auto.conf.cmd').write_text('deps_config :=\n')
release = re.search(r'"([^"]+)"', (stock / 'include/generated/utsrelease.h').read_text())[1]
(dest / 'include/config/kernel.release').write_text(release + '\n')
probe = dest.parent / 'probe'
probe.mkdir(exist_ok=True)
shutil.copy2(ROOT / 'tools/stock_module_probe.c', probe / 'probe.c')
(probe / 'Makefile').write_text('obj-m += probe.o\n')
parser_probe = dest.parent / 'parser-probe'
parser_probe.mkdir(exist_ok=True)
shutil.copy2(ROOT / 'tools/nh_radiotap_kernel_probe.c', parser_probe / 'parser_probe.c')
(parser_probe / 'Makefile').write_text(
    'obj-m += parser_probe.o\n'
    'ccflags-y += -I/work/sources/oneplus-sm8550-modules/vendor/qcom/opensource/wlan/qcacld-3.0/core/hdd/inc\n')
print('Prepared reconstruction:', dest)
print('Kernel release:', release)
print('Module.symvers and vendor build flags are NOT reconstructed here.')

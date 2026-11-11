#!/usr/bin/env python3
"""Extract only named dependency modules from verified stock vendor_boot on Mac."""
import struct
from pathlib import Path
import lz4.block

ROOT = Path(__file__).resolve().parent.parent
image = (ROOT / 'research/europe-h19-reference/vendor_boot.img').read_bytes()
assert image[:8] == b'VNDRBOOT'
version, page = struct.unpack_from('<II', image, 8)
assert version == 4
size = struct.unpack_from('<I', image, 24)[0]
compressed = image[page:page + size]
assert compressed[:4] == b'\x02\x21\x4c\x18'  # Legacy LZ4 blocks, max 8MiB.
offset = 4
blocks = []
while offset + 4 <= len(compressed):
    n = struct.unpack_from('<I', compressed, offset)[0]
    offset += 4
    if n == 0:
        break
    assert 0 < n <= 16 * 1024 * 1024 and offset + n <= len(compressed)
    blocks.append(lz4.block.decompress(compressed[offset:offset + n], uncompressed_size=8 * 1024 * 1024))
    offset += n
archive = b''.join(blocks)
wanted = {'qcom_iommu_util.ko', 'oplus_project.ko'}
out = ROOT / 'research/kernel-audit/stock-build/vendor-modules'
offset = 0
found = []
while offset + 110 <= len(archive):
    assert archive[offset:offset + 6] in (b'070701', b'070702'), offset
    fields = [int(archive[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
    file_size, name_size = fields[6], fields[11]
    name = archive[offset + 110:offset + 110 + name_size - 1].decode()
    offset = (offset + 110 + name_size + 3) & ~3
    if name == 'TRAILER!!!':
        break
    if Path(name).name in wanted:
        data = archive[offset:offset + file_size]
        assert data[:4] == b'\x7fELF'
        (out / Path(name).name).write_bytes(data)
        found.append(name)
    offset = (offset + file_size + 3) & ~3
print('Extracted dependency modules:', found)
assert {Path(n).name for n in found} == wanted

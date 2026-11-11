"""Compare European AVB metadata with the connected stock phone, read-only."""
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
import avbtool

avb = avbtool.Avb()


def load(images, name):
    image = avbtool.ImageHandler(str(images / f'{name}.img'), read_only=True)
    footer, header, descriptors, _ = avb._parse_image(image)
    blob = avb._load_vbmeta_blob(image)
    if not avbtool.verify_vbmeta_signature(header, blob):
        raise ValueError(f'Invalid AVB signature: {name}')
    start = header.SIZE + header.authentication_data_block_size + header.public_key_offset
    key = blob[start:start + header.public_key_size]
    return image, header, descriptors, blob, key


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', type=Path)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', help='Select a device if more than one is connected')
    args = parser.parse_args()
    images = args.images.resolve()
    adb = [args.adb] + (['-s', args.serial] if args.serial else [])
    keys = ('ro.boot.vbmeta.digest', 'ro.boot.vbmeta.hash_alg',
            'ro.boot.vbmeta.size', 'ro.boot.verifiedbootstate',
            'ro.boot.flash.locked', 'ro.boot.slot_suffix', 'ro.build.fingerprint')
    cmd = '; '.join(f'printf "{k}="; getprop {k}' for k in keys)
    output = subprocess.check_output([*adb, 'shell', cmd], text=True)
    phone = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
    if phone['ro.boot.verifiedbootstate'] != 'green' or phone['ro.boot.flash.locked'] != '1':
        raise ValueError('Phone is not locked and in green verified boot state')
    if phone['ro.boot.vbmeta.hash_alg'] != 'sha256':
        raise ValueError('Unexpected device digest algorithm')
    root_image, root_header, descriptors, root_blob, _ = load(images, 'vbmeta')
    if root_header.flags != 0:
        raise ValueError('AVB verification flags are disabled')
    blobs = [root_blob]
    verified_signatures = ['vbmeta']
    all_descriptors = list(descriptors)
    for desc in descriptors:
        if not isinstance(desc, avbtool.AvbChainPartitionDescriptor):
            continue
        name = desc.partition_name
        _, header, child_descriptors, blob, key = load(images, name)
        if key != desc.public_key:
            raise ValueError(f'Chained public key mismatch: {name}')
        if any(isinstance(d, avbtool.AvbChainPartitionDescriptor) for d in child_descriptors):
            raise ValueError('Unexpected nested chain; extend traversal before verification')
        blobs.append(blob)
        verified_signatures.append(name)
        all_descriptors.extend(child_descriptors)
    digest = hashlib.sha256(b''.join(blobs)).hexdigest()
    size = sum(len(b) for b in blobs)
    cli_digest = io.StringIO()
    avb.calculate_vbmeta_digest(str(images / 'vbmeta.img'), 'sha256', cli_digest)
    if digest != cli_digest.getvalue().strip():
        raise ValueError('Manual chain traversal disagrees with official avbtool')
    if digest != phone['ro.boot.vbmeta.digest'] or size != int(phone['ro.boot.vbmeta.size']):
        raise ValueError(f'Phone AVB chain mismatch: candidate {digest}, size {size}')
    covered = {}
    for name in ('boot', 'init_boot'):
        hashes = [d for d in all_descriptors
                  if isinstance(d, avbtool.AvbHashDescriptor) and d.partition_name == name]
        if len(hashes) != 1 or not hashes[0].digest:
            raise ValueError(f'Missing or ambiguous authenticated hash: {name}')
        desc = hashes[0]
        with redirect_stdout(sys.stderr):
            verified = desc.verify(str(images), '.img', {}, root_image, False)
        if not verified:
            raise ValueError(f'AVB content hash failed: {name}')
        covered[name] = {'authenticated_image_bytes': desc.image_size,
                         'salted_avb_digest': desc.digest.hex()}
    file_hashes = {}
    for name in ('boot', 'init_boot', 'vbmeta'):
        with (images / f'{name}.img').open('rb') as f:
            file_hashes[name] = hashlib.file_digest(f, 'sha256').hexdigest()
    report = {
        'result': 'MATCH: European AVB-authenticated boot and init_boot contents and vbmeta structures match the installed locked/green build',
        'observed_vbmeta_digest': phone['ro.boot.vbmeta.digest'],
        'calculated_vbmeta_digest': digest,
        'calculated_vbmeta_bytes': size,
        'verified_metadata_signatures': verified_signatures,
        'chain_public_keys_verified': True,
        'authenticated_image_hashes': covered,
        'extracted_file_sha256': file_hashes,
        'phone_modified': False,
        'scope_limit': 'Does not establish byte-for-byte equality of unused partition padding, a North American full OTA, or equivalence of every regional partition.',
    }
    print(json.dumps(report, indent=2))

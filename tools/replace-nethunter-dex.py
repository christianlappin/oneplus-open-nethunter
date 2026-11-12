#!/usr/bin/env python3
"""Repack the pinned NetHunter APK with only the rebuilt classes3.dex."""

import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile

ORIGINAL_SHA256 = "8bd29db16a06f22c3ef341849bd13b73338d0be1f4f8a75bab5d50b0fbf52f10"
DEX = "classes3.dex"


def signature_entry(name):
    upper = name.upper()
    return upper.startswith("META-INF/") and (
        upper.endswith((".SF", ".RSA", ".DSA", ".EC")) or upper == "META-INF/MANIFEST.MF"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("rebuilt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.original.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        parser.error("original APK does not match the tested 2026.3 release")

    with ZipFile(args.original) as original, ZipFile(args.rebuilt) as rebuilt:
        replacement = rebuilt.read(DEX)
        if replacement == original.read(DEX):
            parser.error("rebuilt dex matches the original")
        with ZipFile(args.output, "x") as output:
            for entry in original.infolist():
                if not signature_entry(entry.filename):
                    data = replacement if entry.filename == DEX else original.read(entry)
                    output.writestr(entry, data)


if __name__ == "__main__":
    main()

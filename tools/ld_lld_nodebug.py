#!/usr/bin/python3
"""Use explicitly prepared debug-free copies for the WLAN full-LTO archive."""
import os
import sys

real = '/work/tools/toolchains/clang-r450784e/bin/ld.lld'
old = os.environ.get('NH_LTO_ORIGINAL_ARCHIVE')
new = os.environ.get('NH_LTO_NODEBUG_ARCHIVE')
args = sys.argv[1:]
if '--whole-archive' in args and old and new:
    if old in args:
        if not os.path.isfile(new):
            raise SystemExit('Missing prepared debug-free LTO archive')
        args = [new if arg == old else arg for arg in args]
os.execv(real, [real, *args])

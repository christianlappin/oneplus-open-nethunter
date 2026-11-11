#!/bin/sh
set -eu
cd /work
mkdir -p build/native
cc -O2 -Wall -Wextra -Werror \
    -Itools/toolchains/clang-r450784e/include tools/strip_llvm_debug.c \
    -Ltools/toolchains/clang-r450784e/lib64 \
    -Wl,-rpath,/work/tools/toolchains/clang-r450784e/lib64 \
    -l:libLLVM-14git.so -o build/native/strip_llvm_debug
python3 tools/prepare_wlan_nodebug_lto.py

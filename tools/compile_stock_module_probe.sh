#!/bin/sh
set -eu
cd /work/build/stock-module-env/kernel
export PATH=/work/tools/toolchains/clang-r450784e/bin:$PATH
clang --version
export ARCH=arm64 LLVM=1 LLVM_IAS=1
export srctree=. objtree=. SRCARCH=arm64 CONFIG_SHELL=/bin/sh
export HOSTCC=gcc HOSTCXX=g++ HOSTCFLAGS=-O2 HOSTCXXFLAGS=-O2
export CC='clang --target=aarch64-linux-gnu' LD=ld.lld AR=llvm-ar NM=llvm-nm
export LEX=flex YACC=bison
export KBUILD_CPPFLAGS=-D__KERNEL__
export LINUXINCLUDE='-I./arch/arm64/include -I./arch/arm64/include/generated -I./include -I./arch/arm64/include/uapi -I./arch/arm64/include/generated/uapi -I./include/uapi -I./include/generated/uapi -include ./include/linux/compiler-version.h -include ./include/linux/kconfig.h'
# Compile only external-build host helpers and the harmless probe object.
# No Module.symvers is manufactured and no module is loaded.
make -f scripts/Makefile.build obj=scripts/basic
make -f scripts/Makefile.build obj=scripts/genksyms
make -f scripts/Makefile.build obj=scripts/mod
make -f scripts/Makefile.build obj=scripts scripts/module.lds
make M=/work/build/stock-module-env/probe "${1:-probe.o}" V=1

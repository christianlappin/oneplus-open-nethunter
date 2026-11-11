#!/bin/sh
set -eu
cd /work
apk add --no-cache build-base linux-headers glib-dev bluez-dev pkgconf pax-utils >/dev/null
make -C sources/libglibutil -j4 release pkgconfig >/dev/null
make -C sources/libglibutil install-dev >/dev/null
make -C sources/libgbinder -j4 release pkgconfig >/dev/null
make -C sources/libgbinder install-dev >/dev/null
make -C sources/bluebinder USE_SYSTEMD=0 CFLAGS='-O2 -g -D_GNU_SOURCE' >build/native/bluebinder-build.log 2>&1
cc -std=c11 -Wall -Wextra -Werror -O2 -static -Isources/bluebinder \
    tools/test_bluebinder_pty_transport.c sources/bluebinder/hci_pty.c \
    -o build/native/test_bluebinder_pty_transport
mkdir -p build/native/bluebinder-pty/lib
cp sources/bluebinder/bluebinder build/native/bluebinder-pty/
# Bundle the musl loader and runtime dependency closure for a temporary Android
# test directory. No Android system files or partitions are changed.
ldd sources/bluebinder/bluebinder >build/native/bluebinder-dependencies.txt
awk '/=>/ {print $3}' build/native/bluebinder-dependencies.txt | while IFS= read -r lib; do
    cp -L "$lib" build/native/bluebinder-pty/lib/
done
cp /lib/ld-musl-aarch64.so.1 build/native/bluebinder-pty/lib/
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -O2 \
    tools/inspect_hci_controller.c -lbluetooth \
    -o build/native/bluebinder-pty/inspect_hci_controller
cp -L /usr/lib/libbluetooth.so.3 build/native/bluebinder-pty/lib/

# Rebuilding the external WLAN module and Bluetooth bridge

The WLAN build targets the Android 16 CPH2551 stock kernel release in the README. It uses Android Clang 14.0.7 r450784e with the recovered kernel configuration and headers. The OnePlus source checkouts and the device inputs both matter. These steps reconstruct an external-module environment. A clean independent rebuild of this public checkout has yet to be demonstrated.

## Check out the source

Run from the repository root:

```sh
checkout() {
  dest=$1 url=$2 rev=$3
  git init -q "$dest"
  git -C "$dest" remote add origin "$url"
  git -C "$dest" fetch --depth 1 origin "$rev"
  git -C "$dest" checkout --detach FETCH_HEAD
}
mkdir -p sources
checkout sources/oneplus-sm8550-common https://github.com/OnePlusOSS/android_kernel_common_oneplus_sm8550.git 298ff0fe2773d325121e88567c10d89f44c02018
checkout sources/oneplus-sm8550-msm https://github.com/OnePlusOSS/android_kernel_oneplus_sm8550.git af83993c92d60aa00dbeb9af99673cc688610c32
checkout sources/oneplus-sm8550-modules https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8550.git 14c366394fcb2dff66a7104b869108a68d58fa02
git -C sources/oneplus-sm8550-modules apply ../../patches/oneplus-wlan.patch
```

OnePlus also publishes the [device build manifest](https://github.com/OnePlusOSS/kernel_manifest/blob/oneplus/sm8550/oneplus_open_b.xml).

## Reconstruct the stock build inputs

Use your own rooted test device running the exact target build. First verify the stock boot reference using the [firmware procedure](firmware.md). The commands below collect inputs through ADB from Android and read a locally extracted boot image. Root through Magisk is required for device paths restricted to root.

```sh
audit=research/kernel-audit
stock="$audit/stock-build"
mkdir -p "$stock/headers" "$stock/vendor-modules" research/europe-h19-reference
adb shell uname -r
adb exec-out su -mm -c 'cat /proc/config.gz' | gzip -dc > "$audit/stock.config"
adb exec-out su -mm -c 'cat /sys/kernel/kheaders.tar.xz' > "$stock/kheaders.tar.xz"
adb exec-out su -mm -c 'cat /sys/kernel/btf/vmlinux' > "$stock/vmlinux.btf"
tar -xJf "$stock/kheaders.tar.xz" -C "$stock/headers"
cp docs/header-source-comparison.json "$stock/"
adb exec-out su -mm -c 'cat /vendor_dlkm/lib/modules/qca_cld3_kiwi_v2.ko' > "$audit/qca_cld3_kiwi_v2.stock.ko"
python3 tools/check_wlan_module_abi.py "$audit/qca_cld3_kiwi_v2.stock.ko" > "$audit/kiwi-stock-abi.json"

for module in cfg80211 cnss2 cnss_nl cnss_plat_ipc_qmi_svc cnss_prealloc cnss_utils qcom_va_minidump wlan_firmware_service; do
  module_path=$(adb shell "find /vendor_dlkm/lib/modules /system_dlkm/lib/modules -name '$module.ko' 2>/dev/null | head -n 1" | tr -d '\r')
  test -n "$module_path" || break
  adb exec-out su -mm -c "cat '$module_path'" > "$stock/vendor-modules/$module.ko"
done
cp inputs/europe-h19/vendor_boot.img research/europe-h19-reference/
python3 -m pip install lz4
python3 tools/extract_vendor_boot_modules.py
```

The running kernel must expose the header archive. If the path is absent, obtain it from the same build with the OEM header module loaded. Confirm all ten vendor dependency modules are present. Verify the header archive SHA-256 is `9fe160c0ff5534a1ebaa56d644073cdfa4fa5c1f9478ba2a9c40e03bd5b2f59e` and the base BTF SHA-256 is `a55170703a1b6d6c46739cdc0d4350ea4f3189cb615a1b8ac3b345d17e2f7bb3`.

Extract the kernel from the verified v4 boot image and recover its exports. Use [vmlinux-to-elf](https://github.com/marin-m/vmlinux-to-elf) at `6aa8039ae67ccc7f49d019d6b18d016f0cc4af80` in an isolated Python environment.

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib
import struct

image = Path("inputs/europe-h19/boot.img").read_bytes()
assert image[:8] == b"ANDROID!"
assert struct.unpack_from("<I", image, 40)[0] == 4
size = struct.unpack_from("<I", image, 8)[0]
kernel = image[4096:4096 + size]
assert hashlib.sha256(kernel).hexdigest() == "d6cf4dbcb87275ee371953e9f75f657592d552627d1731854f72247e280282a3"
Path("research/kernel-audit/stock-build/Image").write_bytes(kernel)
PY
vmlinux-to-elf "$stock/Image" "$stock/vmlinux.recovered.elf"
python3 tools/recover_stock_kernel_exports.py
python3 tools/recover_vendor_exports.py
```

## Build and check

Download the Linux x86 Android Clang r450784e archive from the [Android prebuilts repository](https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/) at `9f759dee5cdc5f85d076c642a192f6a9232f7058`. The reference archive SHA-256 was `b22172346cd3b34317f67d2d7c455cb25bba70177dbc4aed02394ef80c407eb2`. Extract the toolchain so that `tools/toolchains/clang-r450784e/bin/clang` is executable in a Linux x86-64 container. Then run:

```sh
docker build --platform linux/amd64 -f tools/stock-module-builder.Dockerfile \
  -t nethunter-stock-module-builder:bookworm .
sh tools/build-wlan.sh
```

The output is `kiwi_v2.ko` under the Qualcomm driver directory in the modules checkout. The script checks the candidate against independently recovered export CRCs and stock callback layouts. The on-device launcher also pins the kernel release and the hashes of the stock and previously tested replacement modules. A build with a different digest needs its own runtime validation before being treated as equivalent to the tested artifact.

## Build the Bluebinder bridge

Use the same `checkout` function from above:

```sh
checkout sources/bluebinder https://github.com/mer-hybris/bluebinder.git ebab7c3c3fb15f0eea4db0ff14837066a716f973
checkout sources/libgbinder https://github.com/mer-hybris/libgbinder.git 770f4ce2a5aca0bcaf4df2ba58e21fa30e74b1bc
checkout sources/libglibutil https://github.com/sailfishos/libglibutil.git fa82adf84ba308626c4389c6e5b95bb4c12ce1d6
git -C sources/bluebinder apply ../../patches/bluebinder-pty.patch
mkdir -p build/native
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  alpine:3.22 sh tools/build_bluebinder_pty.sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  alpine:3.22 build/native/test_bluebinder_pty_transport
```

The bridge output and its runtime libraries are in `build/native/bluebinder-pty`. The Android helper expects this bundle under `/data/adb/nh-open/bluebinder` and gives Kali temporary ownership of the internal controller.

## NetHunter app scripts and host tests

The two NetHunter patches use paths relative to an installed app directory that contains `scripts/`. Apply them to copies of the matching app assets first. The host settings patch preserves Android mount flags and leaves Android's global DNS configuration alone. The USB patch sets the mouse boot interface subclass to 1 and mouse protocol to 2.

Run the parser and policy tests with a host C compiler:

```sh
mkdir -p build
for test in radiotap tx_policy; do
  cc -std=c11 -Wall -Wextra -Werror -Idevelopment/wlan-monitor-tx \
    "tools/test_nh_${test}.c" -o "build/test_nh_${test}"
  "build/test_nh_${test}"
done
```

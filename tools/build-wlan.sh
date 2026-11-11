#!/bin/sh
# Host-side build only. Apply patches/oneplus-wlan.patch before running this.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
build_dir=research/kernel-audit/stock-build
stock=research/kernel-audit/qca_cld3_kiwi_v2.stock.ko
driver=sources/oneplus-sm8550-modules/vendor/qcom/opensource/wlan/qcacld-3.0
image=nethunter-stock-module-builder:bookworm
kernel_release=5.15.180-android13-8-o-01177-gea9ad0c186c5

test -r "$build_dir/Module.symvers.recovered"
test -r "$stock"
test -f "$driver/core/hdd/src/wlan_hdd_nh_tx.c"
python3 tools/prepare_stock_module_env.py
cp "$build_dir/Module.symvers.recovered" build/stock-module-env/kernel/Module.symvers

container() {
    docker run --rm --platform linux/amd64 -v "$PWD:/work" -w /work \
        -e NH_MONITOR_TX=y "$image" "$@"
}
container sh tools/compile_stock_module_probe.sh modules
container sh tools/compile_wlan_stock_object.sh kiwi_v2.o
python3 tools/inspect_cfg80211_btf.py > "$build_dir/cfg80211-stock-struct-layout.json"
container python3 tools/probe_cfg80211_layout.py
container sh tools/link_wlan_candidate.sh
python3 tools/check_wlan_module_abi.py "$stock" "$driver/kiwi_v2.ko" \
    --symvers "$build_dir/Module.symvers.recovered" --kernel-release "$kernel_release"
python3 tools/check_wlan_ops_layout.py "$stock" "$driver/kiwi_v2.ko"

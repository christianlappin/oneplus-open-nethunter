#!/bin/sh
set -eu
cd /work
sh tools/prepare_wlan_lto_inputs.sh
export WLAN_LINKER=/work/tools/ld_lld_nodebug.py
export NH_LTO_ORIGINAL_ARCHIVE=/work/sources/oneplus-sm8550-modules/vendor/qcom/opensource/wlan/qcacld-3.0/kiwi_v2.o
export NH_LTO_NODEBUG_ARCHIVE=/work/build/wlan-nodebug-lto/kiwi_v2.nodebug.a
sh tools/compile_wlan_stock_object.sh modules

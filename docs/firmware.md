# Firmware reference and verification

OnePlus lists the same marketing build string for its IN, EU, and NA rollouts. Record the product and OTA ID as well as the version. The tested North American phone reported `CPH2551_11.H.19_3190_202603051130`. The North American full OTA for that exact build was unavailable during this work. [OnePlus rollout announcement](https://community.oneplus.com/circle/1440398960022781957)

The European full OTA used for comparison is `CPH2551_11.H.19_3190_202603051128`, file `e6fe3b489fe040d6816da18e14a63dd5.zip`. The catalog provides the download location. Use the package as an extraction input. [European OTA catalog entry](https://fwatlas.com/es/oneplus/oneplus-open/cph2551-16-0-3-505-ex01-cph2551-11-h-19-3190-202603051128-eu)

## Extract and check the reference

Use [payload-dumper-go](https://github.com/ssut/payload-dumper-go) with payload hash verification enabled. From this repo's root, set the ZIP path and extract:

```sh
ota_zip=/absolute/path/to/e6fe3b489fe040d6816da18e14a63dd5.zip
mkdir -p inputs/europe-h19
unzip -p "$ota_zip" payload.bin > inputs/europe-h19/payload.bin
payload-dumper-go -p boot,init_boot,vbmeta,vbmeta_system,vbmeta_vendor,vendor_boot,dtbo,recovery \
  -o inputs/europe-h19 inputs/europe-h19/payload.bin
(cd inputs/europe-h19 && shasum -a 256 -c ../../docs/firmware-sha256.txt)
```

For the device comparison, connect a phone running the target build with its bootloader locked and Android Verified Boot green. Enable USB debugging and accept the host prompt. Run:

```sh
python3 tools/verify_european_boot_baseline.py inputs/europe-h19
```

The script reads boot properties through ADB, verifies the candidate signatures and chain keys, compares the chain digest and size against the running device, and checks the signed boot and init_boot content hashes. It uses [Android Verified Boot](https://android.googlesource.com/platform/external/avb/) tooling. A single device is selected by default. Use `--serial` locally when multiple devices are attached.

The measured chain digest was `acd7e2a0871d79a3b047b1a512973a5e1ab1a5320e59d6b574234fd0922de801` over 24,448 bytes of metadata. The signed descriptors covered 54,128,640 bytes of boot and 2,338,816 bytes of init_boot. This establishes a match for those authenticated contents and the verified metadata chain on the tested build. It leaves unused padding and other regional partitions outside the comparison.

This release publishes the provenance, extraction procedure, and reference hashes. Obtain the firmware from the source linked above.

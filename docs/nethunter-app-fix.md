# NetHunter BadBluetooth Prefix None fix

In NetHunter 2026.3, selecting **None** in the BadBluetooth **Prefix** menu clears the UAC setting and leaves the previous prefix in effect. For example, switching from **Mobile Home** to **None** can still send Meta+Enter and a final Enter. The [Java patch](../patches/nethunter-badbt-prefix-none.patch) resets the prefix to the sender's no-prefix value.

## Rebuild the APK

Apply the Java patch to the NetHunter app source and build with the project's Android build instructions. The NetHunter 2026.3 APK identifies source revision `1a76629c780675edb0c3d7e7a1386bc93a20ca6f`. For that exact published APK, the following path makes the equivalent edit to the compiled code and preserves the original resources, manifest, libraries and other DEX files.

Use the [official NetHunter 2026.3 APK](https://kalilinux.gitlab.io/nethunter/store/nethunter-store-website/packages/com.offsec.nethunter/), Apktool 2.12.1, Java 17 and Android SDK Build Tools 35. Verify the original APK's signature with the official release certificate before rebuilding. The repacking script checks the exact original SHA-256.

From the root of this repository, with `APKTOOL_JAR` set to the Apktool JAR and the build tools on your PATH:

```sh
original=/absolute/path/to/com.offsec.nethunter_2026100700.apk
work=$(mktemp -d)
java -jar "$APKTOOL_JAR" d -r -o "$work/decoded" "$original"
patch -d "$work/decoded" -p1 < patches/nethunter-2026.3-badbt-prefix-none.smali.patch
java -jar "$APKTOOL_JAR" b "$work/decoded" -o "$work/rebuilt.apk"
python3 tools/replace-nethunter-dex.py "$original" "$work/rebuilt.apk" "$work/repacked.apk"
zipalign -P 16 -f 4 "$work/repacked.apk" "$work/aligned.apk"
apksigner sign --ks /absolute/path/to/your-keystore.jks --out nethunter-fixed.apk "$work/aligned.apk"
apksigner verify --verbose --print-certs nethunter-fixed.apk
```

Android requires a matching signature for an in-place update. [Save the official APK, app data and settings](recovery.md#save-the-official-apk-and-settings-before-switching-builds) before replacing it with your locally signed build. Reinstalling either build under a different signing key requires uninstalling the currently installed one and restoring settings from backup. Keep the signing key private. Future locally signed updates should use the same key. The Kali filesystem and device launchers are separate from the Android app data.

With the patched server files installed, use the [BadBluetooth app procedure](badbluetooth.md). Use an exclusive input receiver to verify the selected preset as keyboard events. See [the test results](results.md) for the tested firmware and scope.

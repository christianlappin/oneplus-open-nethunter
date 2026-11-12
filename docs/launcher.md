# NetHunter Launcher for the OnePlus Open

This Android app provides buttons for the OnePlus Open setup in this repository. It uses the installed `nh-open`, `nh-monitor`, `nh-badbt`, and patched USB Arsenal script. It requests Magisk root and runs the controller from root-owned storage. It runs one launcher session at a time.

## Use the launcher

- **Capture Wi-Fi beacons** lets you pick channel 1, 6, or 11 and a duration of 15, 30, or 60 seconds. It saves a PCAP to **Files → Downloads → NetHunter**. Android Wi-Fi returns when the capture ends. The launcher uses passive mode.
- **Start Bad Bluetooth** can show paired and discoverable Classic Bluetooth devices. Allow **Nearby Devices** and turn on Bluetooth if Android asks. Put your authorized receiver in discoverable mode, choose it, and confirm **Start**. The launcher remembers the address for next time. Manual entry is also available. Once the launcher reports the keyboard is ready, pair with **NH Lab Keyboard** from the receiver. Use **Open NetHunter → Bluetooth Arsenal → Bad Bluetooth** for the sender and presets. The server is already running, so proceed to the send controls.
- **Enable USB keyboard and mouse** asks whether the test computer runs macOS, Linux, or Windows. Connect the computer and start from USB debugging mode with file transfer and tethering off. **Send USB test key** sends one lowercase `n` after confirmation.
- **Restore normal mode** stops the launcher session and returns Wi-Fi and Bluetooth to Android. It also restores ADB-only mode after USB keyboard and mouse use.

## Verified on the OnePlus Open

The capture button saved a valid radiotap PCAP. A 15-second channel 1 run recorded 520 frames and reported zero kernel drops. Wi-Fi returned to Android on both early stop and timeout. The receiver picker discovered an owned Kali laptop, and the saved-receiver option started the keyboard server. The laptop paired and connected to its HID service. Restore normal mode ended the session and returned Bluetooth to Android. On a Mac, the USB picker exposed the keyboard and mouse, the test key arrived exactly once, and Restore normal mode returned USB to ADB-only. The Linux and Windows selections are available in the picker. USB testing for this launcher used macOS.

## Build and install

Use JDK 17, Android SDK Platform 35, Android Build Tools 35, and a signing keystore you control. The build uses the Android SDK's AAPT2, D8, zipalign, and apksigner tools. [Android command-line build documentation](https://developer.android.com/tools/aapt2)

Run from the repo root after setting `JAVA_HOME` to your JDK:

```sh
export ANDROID_JAR=/path/to/android-sdk/platforms/android-35/android.jar
export ANDROID_BUILD_TOOLS=/path/to/android-sdk/build-tools/35.0.0
export KEYSTORE=/path/to/launcher.jks
sh development/oneplus-launcher/build-apk.sh NetHunter-Launcher.apk

adb push development/oneplus-launcher/controller /data/local/tmp/nh-launcher.new
adb shell 'su -mm -c "cp /data/local/tmp/nh-launcher.new /data/adb/nh-open/nh-launcher.new && chmod 0700 /data/adb/nh-open/nh-launcher.new && mv -f /data/adb/nh-open/nh-launcher.new /data/adb/nh-open/nh-launcher && rm /data/local/tmp/nh-launcher.new"'
adb install -r NetHunter-Launcher.apk
```

Open **NetHunter Launcher** from the app drawer and approve its Magisk request. Use the same signing key for future updates. The app requires the device-specific scripts to be installed first. See [BadBluetooth setup](badbluetooth.md), [device build instructions](build.md), and [recovery](recovery.md).

# NetHunter Launcher for the OnePlus Open

This Android app provides buttons for the OnePlus Open setup in this repository. It uses the installed `nh-open`, `nh-monitor`, `nh-badbt`, and patched USB Arsenal script. It requests Magisk root and runs the controller from root-owned storage. It runs one launcher session at a time.

## Use the launcher

- **Capture Wi-Fi beacons** lets you pick a band, channel, and a 15-, 30-, or 60-second preset or a custom duration of 1–1,770 seconds. It saves a PCAP to **Files → Downloads → NetHunter**. Android Wi-Fi returns when the capture ends. The launcher uses passive mode.
- **Scan channels** listens briefly on each selected channel and lists access points whose beacons it hears. Choose **Both bands**, **2.4 GHz only**, or **5 GHz only**. Tap a result to capture beacons from that access point on its channel, or use **Last results** to reopen the list. The launcher filters by access-point address (BSSID), so two entries with the same network name can be captured separately. Results depend on which access points are within range during the scan.
- **Start Bad Bluetooth** can show paired and discoverable Classic Bluetooth devices. Allow **Nearby Devices** and turn on Bluetooth if Android asks. Put your authorized receiver in discoverable mode, choose it, and confirm **Start**. The launcher remembers the address for next time. Manual entry is also available. Once the launcher reports the keyboard is ready, pair with **NH Lab Keyboard** from the receiver. Use **Open NetHunter → Bluetooth Arsenal → Bad Bluetooth** for the sender and presets. The server is already running, so proceed to the send controls.
- **Enable USB keyboard and mouse** asks whether the test computer runs macOS, Linux, or Windows. Connect the computer and start from USB debugging mode with file transfer and tethering off. **Send USB test key** sends one lowercase `n` after confirmation.
- **Restore normal mode** stops the launcher session and returns Wi-Fi and Bluetooth to Android. It also restores ADB-only mode after USB keyboard and mouse use.

The picker covers 2.4 GHz channels 1–11 and 5 GHz channels 36, 40, 44, 48, 149, 153, 157, 161, and 165. It uses the non-DFS 5 GHz channels reported by the tested device.

## Verified on the OnePlus Open

The two-band scan created captures on all 20 requested channels and found access points on both bands. On Launcher 1.1, selecting a 5 GHz channel 44 result saved a channel-wide PCAP with 766 frames reporting 5220 MHz and zero kernel drops. Android Wi-Fi returned after the capture. The manual band picker also completed a 5 GHz channel 36 capture and restored Wi-Fi. That run heard zero beacons.

The capture button saved a valid radiotap PCAP. A 15-second channel 1 run recorded 520 frames and reported zero kernel drops. Wi-Fi returned to Android on both early stop and timeout. The receiver picker discovered an owned Kali laptop, and the saved-receiver option started the keyboard server. The laptop paired and connected to its HID service. Restore normal mode ended the session and returned Bluetooth to Android. On a Mac, the USB picker exposed the keyboard and mouse, the test key arrived exactly once, and Restore normal mode returned USB to ADB-only. The Linux and Windows selections are available in the picker. USB testing for this launcher used macOS.

Launcher 1.2 was tested by selecting a saved scan result for a 5 GHz lab access point and entering a custom 65-second duration. The PCAP contained 452 beacons. Every frame matched the selected BSSID and channel 44. The duration picker also rejected a value above the limit.

In separate passive tests on `nhmon0`, Airodump-ng recorded 103 beacons from the lab access point and Wifite listed it during discovery. Wifite's scan display required an interactive terminal. The test ended before target selection. Active audit workflows remain unverified. [Airodump-ng documentation](https://aircrack-ng.com/doku.php?id=airodump-ng) · [Wifite documentation](https://www.kali.org/tools/wifite/)

## Build and install

Use JDK 17, Android SDK Platform 35, Android Build Tools 35, and a signing keystore you control. The build uses the Android SDK's AAPT2, D8, zipalign, and apksigner tools. [Android command-line build documentation](https://developer.android.com/tools/aapt2)

Stop any launcher session before installing or updating. Run from the repo root after setting `JAVA_HOME` to your JDK:

```sh
export ANDROID_JAR=/path/to/android-sdk/platforms/android-35/android.jar
export ANDROID_BUILD_TOOLS=/path/to/android-sdk/build-tools/35.0.0
export KEYSTORE=/path/to/launcher.jks
sh development/oneplus-launcher/build-apk.sh NetHunter-Launcher.apk

adb push development/oneplus-launcher/controller /data/local/tmp/nh-launcher.new
adb push development/oneplus-launcher/scan-beacons.py /data/local/tmp/nh-scan-beacons.py
adb shell 'su -mm -c "cp /data/local/tmp/nh-launcher.new /data/adb/nh-open/nh-launcher.new && chmod 0700 /data/adb/nh-open/nh-launcher.new && mv -f /data/adb/nh-open/nh-launcher.new /data/adb/nh-open/nh-launcher && rm /data/local/tmp/nh-launcher.new"'
adb shell 'su -mm -c "cp /data/local/tmp/nh-scan-beacons.py /data/adb/nh-open/nh-scan-beacons.py && chmod 0600 /data/adb/nh-open/nh-scan-beacons.py && rm /data/local/tmp/nh-scan-beacons.py"'
adb install -r NetHunter-Launcher.apk
```

Open **NetHunter Launcher** from the app drawer and approve its Magisk request. Use the same signing key for future updates. The app requires the device-specific scripts to be installed first. See [BadBluetooth setup](badbluetooth.md), [device build instructions](build.md), and [recovery](recovery.md).

## Update Kali packages on the phone

End any launcher session with **Restore normal mode**, stop any KeX session, and connect Android to Wi-Fi. Open a root Kali shell in NetHunter Terminal. Refresh APT and review the proposed upgrades, dependencies, and removals.

```sh
apt-get update
apt-get -s full-upgrade
apt-get --download-only full-upgrade
```

After the download succeeds, run the upgrade from the same Kali shell. This procedure keeps locally modified package configuration files and uses a temporary service policy if the chroot has none. The policy prevents package scripts from starting or restarting services during the upgrade.

```sh
(
    set -eu
    export DEBIAN_FRONTEND=noninteractive UCF_FORCE_CONFFOLD=1 NEEDRESTART_MODE=l
    policy=/usr/sbin/policy-rc.d
    if [ ! -e "$policy" ] && [ ! -L "$policy" ]; then
        temporary=$(mktemp /usr/sbin/.nh-update-policy.XXXXXX)
        cleanup() {
            if [ "$temporary" -ef "$policy" ]; then rm -f "$policy"; fi
            rm -f "$temporary"
        }
        trap cleanup EXIT
        trap 'exit 130' HUP INT TERM
        printf '#!/bin/sh\nexit 101\n' >"$temporary"
        chmod 755 "$temporary"
        ln "$temporary" "$policy"
    fi
    apt-get --no-download -o Dpkg::Options::=--force-confold full-upgrade
    dpkg --audit
    apt-get check
    apt-get -s full-upgrade
)
```

Open NetHunter from the launcher and test a short passive capture. Confirm that Android reconnects to Wi-Fi after the capture. See the [post-upgrade results](results.md#kali-upgrade-on-the-phone) for the checks run on this build. [Kali package update guide](https://www.kali.org/docs/general-use/updating-kali/)

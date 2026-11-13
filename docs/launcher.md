# NetHunter Launcher for the OnePlus Open

This Android app provides buttons for the OnePlus Open setup in this repository. It uses the installed `nh-open`, `nh-monitor`, `nh-badbt`, and patched USB Arsenal script. It requests Magisk root and runs the controller from root-owned storage. It runs one launcher session at a time.

## Use the launcher

- **Capture Wi-Fi beacons** lets you pick a band, channel, and a 15-, 30-, or 60-second preset or a custom duration of 1–1,770 seconds. It saves a PCAP to **Files → Downloads → NetHunter**. Android Wi-Fi returns when the capture ends. The launcher uses passive mode.
- **Scan channels** listens briefly on each selected channel and lists access points whose beacons it hears. Choose **Both bands**, **2.4 GHz only**, or **5 GHz only**. Tap a result to choose **Capture beacons**, **Capture lab traffic**, or a targeted **Airodump-ng survey**. Use **Last results** to reopen the list. The launcher filters by access-point address (BSSID), so two entries with the same network name can be captured separately. Results depend on which access points are within range during the scan.
- **Capture lab traffic** records management, control, and data frames with the selected access point in an 802.11 address field. Use it on an authorized lab network. Generate normal traffic from a lab client during capture. If you need to observe an association, reconnect a client you control. This mode never transmits. A capture can contain no EAPOL frames or only part of an exchange.
- **Airodump-ng survey** records one channel and saves both a PCAP and a CSV. Start from the home screen for a channel survey, or from a scan result to select one AP. A targeted survey filters the saved PCAP to frames involving the selected BSSID. The CSV contains Airodump’s survey results. Use **Capture lab traffic** when you need radiotap headers.
- **Analyze capture** reads a saved launcher PCAP with TShark and shows frame counts, EAPOL count, and advertised security, authentication suites, and protected management frames (PMF). Launcher 1.4 labels WPA2-Personal, WPA3-Personal (SAE), WPA2/WPA3-Personal transition, and Enhanced Open (OWE). PMF can be required, optional, disabled, unknown, or inconsistent. It also shows channel and signal when present. The summary uses the advertised RSN information in beacons or probe responses. Use Wireshark to inspect what a client negotiated, or to inspect Wi-Fi 7 RSN override elements. EAPOL counts do not certify a complete handshake. Open larger files in Wireshark.
- **Start Bad Bluetooth** can show paired and discoverable Classic Bluetooth devices. Allow **Nearby Devices** and turn on Bluetooth if Android asks. Put your authorized receiver in discoverable mode, choose it, and confirm **Start**. The launcher remembers the address for next time. Manual entry is also available. Once the launcher reports the keyboard is ready, pair with **NH Lab Keyboard** from the receiver. Use **Open NetHunter → Bluetooth Arsenal → Bad Bluetooth** for the sender and presets. The server is already running, so proceed to the send controls.
- **Enable USB keyboard and mouse** asks whether the test computer runs macOS, Linux, or Windows. Connect the computer and start from USB debugging mode with file transfer and tethering off. **Send USB test key** sends one lowercase `n` after confirmation.
- **Restore normal mode** stops the launcher session and returns Wi-Fi and Bluetooth to Android. It also restores ADB-only mode after USB keyboard and mouse use.

The picker covers 2.4 GHz channels 1–11 and 5 GHz channels 36, 40, 44, 48, 149, 153, 157, 161, and 165. It uses the non-DFS 5 GHz channels reported by the tested device.

## Which app to use in the field

The OnePlus-specific controls live in **NetHunter Launcher**. The NetHunter app continues to host its built-in features, including KeX Manager and Arsenal. Tools in the Kali chroot do not automatically become pages in NetHunter’s drawer. Everything below can run on the phone.

| Task | Where to open it |
| --- | --- |
| Find a channel or AP, save a capture, stop the radio session | **NetHunter Launcher → Scan channels** or **Airodump-ng survey** |
| Read channel, signal, advertised security and PMF | **NetHunter Launcher → Analyze capture** (TShark) |
| Check a saved capture for WPS advertisements | **Wireless tools → Wash · offline WPS check** |
| Inspect a saved capture for authentication material | **Wireless tools → hcxtools · capture details**. The report does not export hashes. |
| Run Wifite discovery on the internal adapter | **Wireless tools → Wifite · discovery → Choose channel**. Pick the band, channel and duration. The launcher creates `nhmon0` and opens Wifite in NetHunter Terminal. Allow the Terminal app’s Magisk prompt if shown. |
| Browse a saved survey in Kismet | **Wireless tools → Kismet · replay capture**. Choose a PCAP and create a Kismet login on first use. The browser connects to the phone’s loopback service. **Restore normal mode** closes it, or it stops after 15 minutes. |
| Inspect individual packets and protocol fields | **NetHunter → KeX Manager**. Start the loopback desktop, connect in KeX, open Wireshark and browse to `/sdcard/Download/NetHunter`. [KeX setup](https://www.kali.org/docs/nethunter/nethunter-kex-manager/) |
| Run an interactive audit or use a different capture adapter | **Wireless tools → Open NetHunter Terminal**, then choose **Kali**. Aircrack-ng, Aireplay-ng and Reaver run here. The launcher menu explains each tool. |

TShark, Wireshark and Aircrack-ng can all read saved captures, so Android Wi-Fi can stay connected during analysis. Airodump-ng and the capture buttons temporarily take the internal radio out of Android service. Use **Restore normal mode** if you finish early. Aireplay-ng and Reaver can transmit, and Wifite can start active tests after target selection. Their interactive workflows are kept separate from the capture buttons. Wifite discovery uses receive-only monitor mode and supplies the interface automatically. Use **Restore normal mode** to end it early. Wifite actions that transmit, such as deauthentication, require a separate injection-enabled lab session. Use Airodump-ng for a tap-to-start live survey, or Kismet to replay the saved capture. A separate fixed-channel Kismet test also received packets on the internal adapter. The packaged Kismet version can crash with `--no-plugins`; the launcher avoids that flag. [Kismet issue #602](https://github.com/kismetwireless/kismet/issues/602)

In a Kali shell, install only the packages you are missing:

```sh
apt-get update
apt-get install aircrack-ng wifite kismet wireshark tshark reaver tcpdump
apt-get install --no-install-recommends hcxtools
```

Aircrack-ng includes Airodump-ng and Aireplay-ng. Reaver includes Wash. The optional `hcxtools` package runs offline, so it does not need `hcxdumptool` or a second adapter. [Kali hcxtools package](https://www.kali.org/tools/hcxtools/)

For live Kismet, run a launcher replay once to create its loopback configuration, then stop the replay. In NetHunter Terminal, open an Android root shell and start a timed passive monitor session. This example uses channel 44 (5220 MHz):

```sh
/data/adb/nh-open/wlan/nh-monitor run passive 5220 120
```

When `nhmon0` is ready, use a separate **Kali** terminal session:

```sh
timeout -k 4 90 kismet --no-ncurses-wrapper --no-line-wrap \
  --homedir /root/.nh-kismet --override /root/.nh-kismet/override.conf -n \
  -c 'nhmon0:type=linuxwifi,channel_hop=false,channel=44,ignoreprimary=true'
```

Open `http://127.0.0.1:12501/` in the phone browser. Stop Kismet with **Ctrl+C**, then tap **Restore normal mode** in the launcher. Change both the MHz and the channel together when choosing another frequency. [Kismet Linux Wi-Fi source options](https://www.kismetwireless.net/docs/readme/datasources/wifi-linux/)

## External USB capture on 6 GHz and DFS

On the tested OxygenOS build, the internal PHY reports no 6 GHz or DFS channels. The stock boot kernel has USB host support and a vendor `mac80211.ko`, but the installed module directories contain no `mt76` or `mt7921u` driver. The Kali Kismet 2025.09.R1 package on this phone predates the USB userspace source introduced in [Kismet 2026-10-R1](https://kismetwireless.net/posts/kismet-2026-10-r1/).

The [Panda PAU0F AXE3000](https://www.pandawireless.com/pandaAXE3000dualant.html) and [ALFA AWUS036AXML](https://www.alfa.com.tw/products/awus036axml) are tri-band candidates for passive capture through the newer [Kismet userspace USB source](https://www.kismetwireless.net/docs/readme/datasources/wifi-usb-userspace/). Kismet lists both as Linux options in its [hardware notes](https://www.kismetwireless.net/sharkfest26/). Phone compatibility has yet to be tested with either adapter. To validate a borrowed or returnable unit, confirm its USB ID through an OTG connection, open it using a USB-enabled Kismet build, and capture known AP beacons on the exact 6 GHz and DFS channels needed. That would verify passive capture through Kismet. A native monitor interface for Aircrack-ng tools requires a compatible kernel driver.

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
adb push development/oneplus-launcher/analyze-capture.py /data/local/tmp/nh-analyze-capture.py
adb shell 'su -mm -c "cp /data/local/tmp/nh-launcher.new /data/adb/nh-open/nh-launcher.new && chmod 0700 /data/adb/nh-open/nh-launcher.new && mv -f /data/adb/nh-open/nh-launcher.new /data/adb/nh-open/nh-launcher && rm /data/local/tmp/nh-launcher.new"'
adb shell 'su -mm -c "cp /data/local/tmp/nh-scan-beacons.py /data/adb/nh-open/nh-scan-beacons.py && chmod 0600 /data/adb/nh-open/nh-scan-beacons.py && rm /data/local/tmp/nh-scan-beacons.py"'
adb shell 'su -mm -c "cp /data/local/tmp/nh-analyze-capture.py /data/adb/nh-open/nh-analyze-capture.py && chmod 0600 /data/adb/nh-open/nh-analyze-capture.py && rm /data/local/tmp/nh-analyze-capture.py"'
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

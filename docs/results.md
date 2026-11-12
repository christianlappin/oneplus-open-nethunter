# Verified lab results

Target was a North American CPH2551 running OxygenOS 16.0.3.505(EX01) and stock boot kernel `5.15.180-android13-8-o-01177-gea9ad0c186c5`.

| Test | Observed result |
| --- | --- |
| Stock ABI recovery | 8,833 recovered exports. All 525 imported CRCs in the installed WLAN module matched independently recovered provider exports. |
| Wi-Fi capture | Kali tcpdump captured five beacons each on channels 1, 6 and 11, with zero reported drops. |
| Wi-Fi transmission | A separate monitor-mode receiver confirmed management traffic, raw data, and RTS on channel 1. The aireplay-ng file replay produced five verified frames at 4.97 packets per second, with valid FCS on the verified frames. |
| Wi-Fi restoration | The original WLAN module and Android managed mode were restored after testing. |
| USB HID | A dedicated Mac receiver got the test keyboard string and two opposite mouse movements. ADB-only USB mode returned afterward. |
| Bluetooth in Kali | BlueZ discovery, Bluelog detection of the lab laptop, classic pairing on both ends, and SDP browsing passed. The test bond was removed. |
| BadBluetooth HID | The installed phone launcher bonded with the owned Kali laptop and opened both Classic HID channels. An exclusive evdev receiver confirmed exactly one `KEY_N` press and release plus two opposite relative mouse movements with no buttons. The sender was fixed to omit its implicit Enter in plain-text mode. |
| NetHunter BadBluetooth app | The locally signed, patched 2026.3 APK opened the Bluetooth HID server from the Start button. An exclusive Kali evdev receiver confirmed both built-in preset strings after changing Mobile Home and Linux Terminal to None. All 84 expected characters arrived, with balanced key releases and zero extra shortcuts or Enter presses. Stop ended the session and returned controller ownership to Android. |
| Bluetooth in Android | Android negotiated aptX HD with the laptop. The receiver captured 3.99 seconds of the synthetic media tone, with the expected 697 and 1209 Hz frequencies 25.2 dB above adjacent comparison frequencies. The temporary settings and bond were removed. |
| Phone reboot | Magisk root and NetHunter returned. The boot kernel matched the stock reference and SELinux was enforcing. |
| KeX | The Android KeX client authenticated and connected to a loopback-only XFCE desktop. The temporary profile and server were removed afterward. The owner still chooses credentials for regular use. |

The tested Wi-Fi module SHA-256 was `6e895b099586f384ebc14628889f4a9e0c2e7d495c0f85fd8873e87b220a1f5f`. The stock WLAN module SHA-256 was `b117f692bf9fdd2eecd15d5f50ffc7167e4cc1da7d23f71bb0ec610efd7cfc40`.

The test path enforces a 10 packet-per-second cap. Firmware rewrote Duration to 202 microseconds in the observed data and RTS cases and can retry frames. Other control-frame subtypes, performance at higher rates, and other firmware builds remain outside the verified scope. BadBluetooth CLI and app results apply to an owned Kali receiver. The preset test checked delivered keyboard events. OS-specific prefix execution was outside the test.

## Publication checks

The original publication patches passed application checks against their pinned sources or matching extracted NetHunter app assets. The host radiotap suite passed 100,000 fuzz inputs and the TX admission suite passed 2,048 subtype and truncation inputs. The saved tested WLAN artifact passed its ABI and callback-layout checks, with 63 shared callbacks and zero offset mismatches. The three published image hashes matched the extracted reference files. The public AVB script reproduced the result using the recorded pre-unlock properties as an ADB fixture.

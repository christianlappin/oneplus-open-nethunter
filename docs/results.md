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

## Kali upgrade on the phone

On November 11, 2026, APT downloaded 951 MB over Android Wi-Fi and completed a Kali Rolling full upgrade in the NetHunter chroot. It upgraded 634 packages, installed 12 dependencies, and replaced `libfalcosecurity0t64` with `libfalcosecurity0.23`. The updated `kali-linux-core` metapackage was version `2026.4.2`. The upgrade kept locally modified package configuration files. The temporary service policy used during installation was removed.

| Post-upgrade check | Observed result |
| --- | --- |
| Package integrity | `dpkg --audit` and `apt-get check` passed. A subsequent full-upgrade simulation showed zero pending changes. |
| Android app and launcher | **Open NetHunter** from Launcher 1.1 opened the NetHunter 2026.3 app. |
| Passive capture and Wi-Fi restoration | A 15-second channel 1 capture through the launcher saved a PCAP with 757 packets and zero kernel drops. The stock driver returned and Android reconnected to Wi-Fi without a reboot. |
| BadBluetooth | The launcher started the keyboard server and reached its listening state. Stopping it returned the controller to Android. |
| KeX | TigerVNC 1.16.2 started a temporary XFCE desktop with Xfwm4. A loopback VNC handshake confirmed that the server required password authentication. The temporary session was stopped. |

Kali also loaded the Bluetooth Python dependencies under Python 3.14.7. The phone finished the tests in normal mode with Wi-Fi connected. Follow the [on-phone upgrade procedure](launcher.md#update-kali-packages-on-the-phone) to reproduce the maintenance steps.

## Launcher 1.3 wireless tools

| Test on the phone | Observed result |
| --- | --- |
| Targeted lab capture and TShark | A 30-second channel 44 run saved 745 frames: 283 management, 194 control and 268 data. Every frame referenced the selected AP and reported 5220 MHz. Monitor TX was disabled. The summary showed RSN PSK and zero EAPOL frames. |
| Targeted Airodump-ng survey | A 15-second survey saved a CSV with 140 beacons from the selected AP on channel 44. The saved PCAP contained 468 frames, all referencing the selected AP after filtering. Android Wi-Fi reconnected afterward. |
| Wash and hcxtools | Both opened the saved lab PCAP from the Android menu. Wash found a WPS 2.0 advertisement. hcxtools 7.1.2 parsed the capture and reported insufficient EAPOL frames. No hash file was written. |
| Aircrack-ng and Wireshark | Aircrack-ng parsed a saved beacon PCAP; no password audit was run. Wireshark rendered the same file in a Kali X display on the phone. |
| Kismet replay | The launcher started Kismet with the lab PCAP, opened the phone browser, and bound HTTP only to `127.0.0.1:12501`. Restore normal mode closed the listener. |
| Live Kismet | With the internal adapter fixed to channel 44 in passive mode, Kismet opened `nhmon0` and its local API reported 19 packets for the selected AP. The test stopped Kismet and restored the stock Wi-Fi driver. |
| NetHunter Terminal | The launcher opened the companion Terminal after Android’s first-run notification prompt. |

The requested binaries were present in Kali. The verified Aireplay-ng transmit test is listed above; no new transmit test or Reaver PIN audit was run as part of the launcher checks. Wifite's passive discovery result is described in the [launcher guide](launcher.md#verified-on-the-oneplus-open).

## Launcher 1.4 security summary

The OnePlus analyzer processed nine synthetic beacons with known settings. It identified SAE, SAE Extended Key, WPA2/WPA3 transition, OWE, WPA2-Personal, enterprise 802.1X, and open networks. It distinguished required, optional, disabled, missing, and inconsistent PMF flags, and did not classify a vendor-specific AKM as SAE. The synthetic input used channel 44. The test validates offline decoding and does not measure 6 GHz capture or client negotiation.

## Launcher 1.5 Wifite discovery

On the OnePlus, the Wireless tools menu opened a dedicated NetHunter Terminal session through its Android root profile. The launcher prepared `nhmon0` in receive-only mode on channel 44. Wifite started Airodump-ng on that interface, and its live output contained the lab access point. Restore normal mode stopped Wifite and its capture process and returned Android Wi-Fi to a connected state. A separate timed session also restored Android Wi-Fi when it expired. The test stopped at discovery.

## Launcher 1.6 Wifite modes

Both launcher modes ran on the OnePlus on channel 44. Discovery used `nhmon0` with TX disabled and found the lab AP. Active audit passed the selected lab BSSID to Wifite and enabled monitor TX on the same interface. In the active test, the driver reported seven frames queued on the station backend and eight rejected attempts at the sampled point. The test did not use an independent RF receiver. Restore normal mode ended the sessions and Android Wi-Fi reconnected.

## Launcher 1.7 Wifite duration and injection retest

The OnePlus opened Wifite discovery in **Until stopped** mode and found the lab AP on channel 44. A 600-second custom run also started successfully and was stopped early using Restore normal mode. Android Wi-Fi returned after stopping. A separate test ended the process owning an untimed monitor session and verified that the monitor helper restored the stock driver.

On channel 149 (5745 MHz), the OnePlus queued seven tagged lab data frames. The independent Kali laptop received five frames containing the exact test marker. Its capture limit was five frames. Both devices returned to managed Wi-Fi. A separate channel 1 probe was queued but did not appear in the receiver capture. The channel 149 test verified raw frame injection and did not test Wifite’s individual active audit methods.

## Publication checks

The original publication patches passed application checks against their pinned sources or matching extracted NetHunter app assets. The host radiotap suite passed 100,000 fuzz inputs and the TX admission suite passed 2,048 subtype and truncation inputs. The saved tested WLAN artifact passed its ABI and callback-layout checks, with 63 shared callbacks and zero offset mismatches. The three published image hashes matched the extracted reference files. The public AVB script reproduced the result using the recorded pre-unlock properties as an ADB fixture.

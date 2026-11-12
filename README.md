# OnePlus Open NetHunter on the stock boot kernel

A device-specific research project for Kali NetHunter on the North American OnePlus Open CPH2551. The tested phone ran OxygenOS `CPH2551_16.0.3.505(EX01)`, Android 16, and kernel `5.15.180-android13-8-o-01177-gea9ad0c186c5`.

The phone uses an unlocked bootloader and a Magisk-patched `init_boot`. It retains the OnePlus boot kernel and runs SELinux in enforcing mode. An on-demand launcher temporarily loads a build-specific Qualcomm Wi-Fi module and restores the original vendor driver when the session ends. A separate timed Bluetooth session lets Kali use the internal controller and then returns control to Android.

## Verified on this build

| Area | Result |
| --- | --- |
| Wi-Fi receive | Passive beacon capture on channels 1, 6, and 11 with Kali tcpdump. |
| Wi-Fi transmit | An independent receiver confirmed the tested management, data and RTS frames on channel 1. Five frames from the aireplay-ng file replay were captured at approximately 5 frames per second. The driver caps the test path at 10 packets per second. Firmware can rewrite Duration and retry frames. |
| Bluetooth | Kali discovered and paired with a lab laptop and browsed its SDP services. The BadBluetooth CLI delivered a keyboard press and release and two mouse movements. The patched NetHunter 2026.3 app started the server and both built-in presets delivered exact text with Prefix None. In a separate Android session, the laptop decoded a synthetic media tone over aptX HD. |
| USB HID | A dedicated Mac receiver verified keyboard input and mouse movement. The NetHunter USB Arsenal CLI works with a corrected mouse descriptor. OxygenOS hides the app menu on this build. |
| Boot and KeX | Magisk, NetHunter, and the stock kernel came back after a normal reboot. The Android KeX client authenticated and connected to a temporary loopback XFCE desktop. |

The results apply to this firmware and kernel. Other frame types, higher replay rates, and OS-specific BadBluetooth prefix execution remain outside the verified scope.

## Source provenance

The public OnePlus source checkouts are the starting point for the build. The common and modules trees identify the .500 release in their commit messages. The MSM checkout identifies .400. The tested device is on .505, so reproduction also depends on the matching device inputs and ABI validation.

| Upstream | Checkout |
| --- | --- |
| [OnePlus SM8550 common kernel](https://github.com/OnePlusOSS/android_kernel_common_oneplus_sm8550) | `298ff0fe2773d325121e88567c10d89f44c02018` |
| [OnePlus SM8550 MSM kernel](https://github.com/OnePlusOSS/android_kernel_oneplus_sm8550) | `af83993c92d60aa00dbeb9af99673cc688610c32` |
| [OnePlus SM8550 modules and device tree](https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8550) | `14c366394fcb2dff66a7104b869108a68d58fa02` |
| [Bluebinder](https://github.com/mer-hybris/bluebinder) | `ebab7c3c3fb15f0eea4db0ff14837066a716f973` |
| [Kali NetHunter app](https://gitlab.com/kalilinux/nethunter/apps/kali-nethunter-app) | Reference source `f88d19ac3eb65f6358909dfcbc559bed93d9ddcf`. Device app version 2026.3. |

## Build and verification

- [Firmware source, extraction and AVB verification](docs/firmware.md)
- [Host build and ABI checks](docs/build.md)
- [Android launcher and device pickers](docs/launcher.md)
- [Update Kali packages on the phone](docs/launcher.md#update-kali-packages-on-the-phone)
- [BadBluetooth setup](docs/badbluetooth.md)
- [On-phone recovery and official APK rollback](docs/recovery.md)
- [NetHunter 2026.3 Prefix None app fix](docs/nethunter-app-fix.md)
- [Verified lab results](docs/results.md)
- [Licensing and credits](LICENSE.md)

Maintainer [@christianlappin](https://github.com/christianlappin).

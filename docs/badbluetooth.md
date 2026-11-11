# BadBluetooth on the internal controller

This device uses the timed Bluebinder handoff from the Android root shell. The tested path uses the upstream BadBluetooth command-line server and sender with [this phone patch](../patches/badbt-phone.patch). The NetHunter APK's BadBluetooth start button is a separate entry point and was outside this test.

## Set up the on-device files

Check out [BadBluetooth](https://github.com/yesimxev/badbt) at `08836e291e3895b08b9db8d76449f2692d98722b`. Apply `patches/badbt-phone.patch` in that checkout. In the rooted Kali filesystem, install the patched `btk_server.py`, `send_string.py`, `sdp_record.xml`, `org.thanhle.btkbservice.conf`, and upstream `keymap.py` in `/root/badbt`. Copy `run-badbt.sh` and `bluez-bredr.conf` from `development/badbt` into the same directory. Kali needs BlueZ, D-Bus, Python 3, python3-dbus and python3-gi.

Install `development/nethunter-android16/nh-badbt` as root with mode 0700 at `/data/adb/nh-open/nh-badbt`. This assumes the Bluebinder bundle and `nh-open` helper from the [build guide](build.md) are already installed. The launcher creates a timed Classic Bluetooth session, limits both HID connections to the supplied receiver address, and returns control to Android after stopping its Kali services.

## Run a lab keyboard check

From an Android Magisk root shell, run `/data/adb/nh-open/nh-badbt <receiver Bluetooth address>` in the foreground. Pair the keyboard from the owned receiver. On BlueZ, use a pairing agent for the bond, wait for pairing to complete, and connect the HID service `00001124-0000-1000-8000-00805f9b34fb` explicitly if it did not attach. The receiver should enumerate `NH Lab Keyboard`. Use a dedicated, exclusively grabbed input receiver for the test before sending input.

From a second Android root shell:

```sh
/data/adb/nh-open/nh-open exec python3 /root/badbt/send_string.py n none none
```

Plain-text mode sends exactly the supplied text. The original sender added Enter even in this mode. The test used one letter and checked for both its press and release plus a quiet interval. Stop the foreground session when finished and forget the test keyboard on the receiver. On Android, ordinary pairing and audio become available after the handoff ends.

The same session also verified the server's mouse report path. An exclusive
receiver captured opposite five-unit horizontal movements without button input.
See [the test results](results.md).

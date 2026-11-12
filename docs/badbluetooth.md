# BadBluetooth on the internal controller

This device uses the timed Bluebinder handoff from the Android root shell. The command-line launcher and the NetHunter app both use the upstream BadBluetooth server and sender with [this phone patch](../patches/badbt-phone.patch).

## Set up the on-device files

Check out [BadBluetooth](https://github.com/yesimxev/badbt) at `08836e291e3895b08b9db8d76449f2692d98722b`. Apply `patches/badbt-phone.patch` in that checkout. In the rooted Kali filesystem, install the patched `btk_server.py`, `send_string.py`, `sdp_record.xml`, `org.thanhle.btkbservice.conf`, and upstream `keymap.py` and `kb_client.py` in `/root/badbt`. Copy `run-badbt.sh` and `bluez-bredr.conf` from `development/badbt` into the same directory. Kali needs BlueZ, D-Bus, Python 3, python3-dbus and python3-gi.

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

## Use the NetHunter app

Allow the separate NetHunter Terminal app's file-access prompt on the tested Android 16 build. The main NetHunter app's Music and audio permission is optional for this keyboard workflow.

In an Android Magisk root shell, start the handoff with `/data/adb/nh-open/nh-badbt --app <receiver Bluetooth address>`. Keep the shell open. After the ready message, open **Bluetooth Arsenal → Bad Bluetooth** and tap **Start** within 120 seconds. Pair from the owned receiver and verify exclusive capture before using **Send**. Tap **Stop** when finished. The launcher stops the temporary services and restores Android's ownership of the controller.

For **Prefix → None** on NetHunter 2026.3, use the [app fix](nethunter-app-fix.md). The original app can retain the previous shortcut and send an extra Enter.

## Save a local recovery copy

Install `development/nethunter-android16/nh-badbt-repair` at `/data/adb/nh-open/nh-badbt-repair` with mode 0700. Once the launcher and server have passed your test, make a root-only backup from an Android root shell:

```sh
set -e
umask 077
base=/data/adb/nh-open
backup="$base/badbt-recovery"
test ! -e "$backup"
staged=$(mktemp -d "$base/badbt-recovery.XXXXXX")
trap 'rm -rf "$staged"' EXIT
cp "$base/nh-badbt" "$staged/"
cd /data/local/nhsystem/kali-arm64/root/badbt
cp btk_server.py send_string.py keymap.py kb_client.py sdp_record.xml \
    org.thanhle.btkbservice.conf run-badbt.sh bluez-bredr.conf "$staged/"
(cd "$staged" && sha256sum * > SHA256SUMS && sha256sum -c SHA256SUMS)
mv "$staged" "$backup"
```

After an Arsenal reinstall, tap **Stop** if the server is running. If needed, request the controller back with `/data/adb/nh-open/nh-open bluetooth-stop`. Once the session ends, run `/data/adb/nh-open/nh-badbt-repair --check`. If it reports changed files, run `--restore` and then `--check` with the same helper. This restores the launcher and the listed support files. A changed APK needs the corresponding APK rollback.

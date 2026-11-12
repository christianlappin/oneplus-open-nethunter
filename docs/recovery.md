# Recover NetHunter on the OnePlus Open

Use an Android shell in NetHunter Terminal. Run `su`, approve Magisk if prompted, and check that `id -u` prints `0`. On the tested build, the Terminal needs its file-access permission. If the Terminal is unavailable, use `adb shell` from a previously authorized computer and then run `su`.

## Repair BadBluetooth after an Arsenal reinstall

Tap **Stop** in Bluetooth Arsenal if the server is running. If Kali still owns the Bluetooth controller, run `/data/adb/nh-open/nh-open bluetooth-stop` and wait for the handoff to finish.

```sh
/data/adb/nh-open/nh-badbt-repair --check
```

If it reports missing or changed files, run the following commands. The helper checks its backup and refuses to restore during an active Bluetooth session.

```sh
/data/adb/nh-open/nh-badbt-repair --restore
/data/adb/nh-open/nh-badbt-repair --check
```

See [BadBluetooth setup](badbluetooth.md#save-a-local-recovery-copy) to install the helper and create its root-only backup.

## Save the official APK and settings before switching builds

This procedure applies to the single-user OnePlus Open setup and official NetHunter 2026.3 APK used in the [app fix](nethunter-app-fix.md). Install [the app data restore helper](../development/nethunter-android16/nh-restore-app-data) at `/data/adb/nh-open/nh-restore-app-data` with mode 0700. Save any settings or files stored outside the app's private directories separately.

With BadBluetooth stopped and the official app still installed, run this in an Android root shell:

```sh
(
    set -eu
    umask 077
    pkg=com.offsec.nethunter
    base=/data/adb/nh-open
    backup="$base/nethunter-app-rollback"
    test ! -e "$backup"
    staged=$(mktemp -d "$base/nethunter-app-rollback.XXXXXX")
    trap 'rm -rf "$staged"' EXIT
    am force-stop "$pkg"
    apk=$(pm path "$pkg" | cut -d: -f2-)
    cp "$apk" "$staged/official.apk"
    test "$(sha256sum "$staged/official.apk" | cut -d' ' -f1)" = 8bd29db16a06f22c3ef341849bd13b73338d0be1f4f8a75bab5d50b0fbf52f10
    dumpsys package "$pkg" > "$staged/package-state.txt"
    cmd appops get --user 0 "$pkg" MANAGE_EXTERNAL_STORAGE > "$staged/appops.txt"
    tar -cf "$staged/user_0.tar" -C "/data/user/0/$pkg" .
    tar -cf "$staged/user_de_0.tar" -C "/data/user_de/0/$pkg" .
    (cd "$staged" && sha256sum official.apk user_0.tar user_de_0.tar > SHA256SUMS && sha256sum -c SHA256SUMS)
    mv "$staged" "$backup"
)
```

## Roll back to the official NetHunter APK

The official and locally signed APKs have different certificates. Switching builds requires uninstalling the current NetHunter app. Export any newer settings you need before starting. This restores the saved snapshot and brings back the official release's **Prefix → None** bug. It leaves the separate Terminal app and Kali filesystem in place.

Stop the Bluetooth session, then run from an Android root shell:

```sh
(
    set -eu
    cd /data/adb/nh-open/nethunter-app-rollback
    sha256sum -c SHA256SUMS
    test -s /data/adb/nh-open/nh-restore-app-data
    pm uninstall com.offsec.nethunter
    pm install -S "$(stat -c %s official.apk)" < official.apk
    sh /data/adb/nh-open/nh-restore-app-data
    if grep -q 'MANAGE_EXTERNAL_STORAGE: allow' appops.txt; then
        cmd appops set --user 0 com.offsec.nethunter MANAGE_EXTERNAL_STORAGE allow
    fi
)
```

Reopen NetHunter, approve its Magisk request if prompted, and verify that the home screen and Bluetooth Arsenal open. Android Keystore keys and changes made after the snapshot may need to be set up again. The backup and app data restore were verified on the OnePlus Open during installation of the patched build. The phone stayed on that build after testing.

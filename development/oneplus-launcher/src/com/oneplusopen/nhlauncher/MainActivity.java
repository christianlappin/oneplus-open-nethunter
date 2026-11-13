package com.oneplusopen.nhlauncher;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int PAPER = 0xfff4f2eb;
    private static final int INK = 0xff1b2725;
    private static final int MUTED = 0xff4c5d58;
    private static final int GREEN = 0xff245e50;
    private static final int LINE = 0xffd7dfd8;
    private static final int NEARBY_PERMISSION = 1;
    private static final int ENABLE_BLUETOOTH = 2;
    private static final int MAX_CAPTURE_SECONDS = 1770;
    private static final String MAC_ADDRESS = "([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}";
    private static final String CONTROLLER = "/data/adb/nh-open/nh-launcher";

    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService commands = Executors.newSingleThreadExecutor();
    private TextView statusTitle;
    private TextView statusText;
    private Button capture;
    private Button scan;
    private Button survey;
    private Button analyze;
    private boolean showScanWhenReady;
    private boolean scanForWifite;
    private boolean openKismetWhenReady;
    private Button bluetooth;
    private Button restore;
    private Button usb;
    private Button testKey;
    private boolean foreground;
    private boolean runningCommand;
    private boolean active;
    private boolean usbActive;
    private boolean authenticated;
    private ReceiverPicker receiverPicker;
    private final Runnable refresh = this::readStatus;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        Window window = getWindow();
        window.setStatusBarColor(PAPER);
        window.setNavigationBarColor(PAPER);
        window.getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(PAPER);
        LinearLayout content = column();
        content.setPadding(dp(24), dp(25), dp(24), dp(28));
        scroll.addView(content);
        add(content, label("NetHunter Launcher", 29, INK, true), 0);
        add(content, label("OnePlus Open", 15, MUTED, false), 3);

        LinearLayout status = column();
        status.setPadding(dp(18), dp(16), dp(18), dp(16));
        status.setBackground(shape(0xffe2ece5, LINE, 16));
        statusTitle = label("Connecting", 16, INK, true);
        statusText = label("Waiting for Magisk root access.", 14, MUTED, false);
        statusText.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        add(status, statusTitle, 0);
        add(status, statusText, 6);
        add(content, status, 22);

        capture = button("Capture Wi-Fi beacons", GREEN, Color.WHITE, GREEN, () -> pickBand("wifi"));
        add(content, capture, 20);
        add(content, label("Choose a channel and duration. Saves a PCAP to Downloads.", 14, MUTED, false), 6);

        scan = button("Scan channels", PAPER, GREEN, LINE, this::pickScanBand);
        add(content, scan, 8);

        survey = button("Airodump-ng survey", PAPER, GREEN, LINE, () -> pickBand("survey"));
        add(content, survey, 8);
        analyze = button("Analyze capture", PAPER, GREEN, LINE, () -> pickCapture("summary"));
        add(content, analyze, 8);
        add(content, button("Wireless tools", PAPER, GREEN, LINE, this::showWirelessTools), 8);

        bluetooth = button("Start Bad Bluetooth", INK, Color.WHITE, INK, this::pickReceiver);
        add(content, bluetooth, 17);
        add(content, label("Starts the keyboard for one lab receiver. Send from Bluetooth Arsenal.", 14, MUTED, false), 6);

        usb = button("Enable USB keyboard and mouse", PAPER, INK, LINE, this::pickUsbHost);
        add(content, usb, 17);
        testKey = button("Send USB test key", PAPER, GREEN, LINE, this::confirmUsbTest);
        add(content, testKey, 8);

        restore = button("Restore normal mode", 0xfffaf9f5, INK, LINE,
            () -> action("stop", "Restoring normal mode…"));
        add(content, restore, 17);
        add(content, button("Open NetHunter", PAPER, GREEN, LINE, this::openNetHunter), 9);
        add(content, button("View session log", PAPER, MUTED, PAPER, this::showLog), 4);
        setContentView(scroll);
        updateButtons();
    }

    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        readStatus();
    }

    @Override protected void onPause() {
        foreground = false;
        main.removeCallbacks(refresh);
        if (receiverPicker != null) receiverPicker.close();
        super.onPause();
    }

    @Override protected void onDestroy() {
        commands.shutdown();
        super.onDestroy();
    }

    private static final int[] CHANNELS_24 = {
        2412, 2417, 2422, 2427, 2432, 2437, 2442, 2447, 2452, 2457, 2462
    };
    private static final int[] CHANNELS_5 = {
        5180, 5200, 5220, 5240, 5745, 5765, 5785, 5805, 5825
    };

    private void pickBand(String mode) {
        new AlertDialog.Builder(this).setTitle("Choose a Wi-Fi band")
            .setItems(new String[] {"2.4 GHz", "5 GHz"}, (dialog, which) ->
                pickChannel(mode, which == 0 ? CHANNELS_24 : CHANNELS_5))
            .setNegativeButton("Cancel", null).show();
    }

    private static String channelLabel(int frequency) {
        boolean lowBand = frequency < 2500;
        int channel = (frequency - (lowBand ? 2407 : 5000)) / 5;
        return "Channel " + channel + " · " + (lowBand ? "2.4 GHz" : "5 GHz");
    }

    private void pickChannel(String mode, int[] frequencies) {
        String[] channels = new String[frequencies.length];
        for (int index = 0; index < channels.length; index++) {
            channels[index] = channelLabel(frequencies[index]);
        }
        new AlertDialog.Builder(this).setTitle("Choose a Wi-Fi channel")
            .setItems(channels, (dialog, which) -> pickDuration(mode, frequencies[which], "", ""))
            .setNegativeButton("Cancel", null).show();
    }

    private void pickScanBand() {
        pickScanBand(false);
    }

    private void pickScanBand(boolean forWifite) {
        String[] bands = {"Both bands", "2.4 GHz only", "5 GHz only"};
        String[] arguments = {"all", "24", "5"};
        new AlertDialog.Builder(this).setTitle("Scan channels")
            .setItems(bands, (dialog, which) -> {
                scanForWifite = forWifite;
                showScanWhenReady = true;
                action("scan " + arguments[which], "Starting passive scan…");
            })
            .setNeutralButton("Last results", (dialog, which) -> showScanResults(forWifite))
            .setNegativeButton("Cancel", null).show();
    }

    private void showScanResults(boolean forWifite) {
        commands.execute(() -> {
            Result result = run("scan-results");
            List<Integer> frequencies = new ArrayList<>();
            List<String> addresses = new ArrayList<>();
            List<String> names = new ArrayList<>();
            List<String> labels = new ArrayList<>();
            if (result.code == 0) {
                for (String line : result.output.split("\n")) {
                    String[] fields = line.split("\t", 3);
                    if (fields.length != 3 || !fields[0].matches("[0-9]{4}") ||
                        !fields[1].matches(MAC_ADDRESS)) continue;
                    int frequency = Integer.parseInt(fields[0]);
                    frequencies.add(frequency);
                    addresses.add(fields[1]);
                    names.add(fields[2]);
                    labels.add(fields[2] + "\n" + channelLabel(frequency) + " · " + fields[1]);
                }
            }
            main.post(() -> {
                if (!foreground || active || runningCommand) return;
                AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                    .setTitle("Networks found").setNegativeButton("Close", null);
                if (labels.isEmpty()) {
                    dialog.setMessage(result.code == 0
                        ? "No beacons were heard during the scan."
                        : "Run a channel scan first.");
                } else {
                    dialog.setItems(labels.toArray(new String[0]), (unused, which) -> {
                        int frequency = frequencies.get(which);
                        String address = addresses.get(which);
                        String name = names.get(which);
                        if (forWifite) confirmWifiteAudit(frequency, address, name);
                        else pickAccessPointAction(frequency, address, name);
                    });
                }
                dialog.show();
            });
        });
    }

    private void pickAccessPointAction(int frequency, String address, String name) {
        String[] modes = {"wifi", "lab", "survey"};
        new AlertDialog.Builder(this).setTitle(name + " · " + channelLabel(frequency))
            .setItems(new String[] {"Capture beacons", "Capture lab traffic", "Airodump-ng survey"},
                (dialog, which) -> {
                    if (which != 1) {
                        pickDuration(modes[which], frequency, address, name);
                    } else {
                        new AlertDialog.Builder(this).setTitle("Capture lab traffic")
                            .setMessage("Record management, control, and data frames involving the selected access point. Use a network you own or are authorized to audit.")
                            .setPositiveButton("Choose duration", (confirm, button) ->
                                pickDuration("lab", frequency, address, name))
                            .setNegativeButton("Cancel", null).show();
                    }
                })
            .setNegativeButton("Cancel", null).show();
    }

    private void pickDuration(String mode, int frequency, String address, String name) {
        String[] labels = {"15 seconds", "30 seconds", "60 seconds", "Custom duration", "Until stopped"};
        int[] seconds = {15, 30, 60};
        String title = mode.equals("wifite") ? (address.isEmpty() ? "Wifite discovery duration" : "Wifite audit duration")
            : mode.equals("survey") ? "Airodump-ng survey duration"
            : mode.equals("lab") ? "Capture " + name + " lab traffic"
            : address.isEmpty() ? "Capture duration" : "Capture " + name + " beacons";
        new AlertDialog.Builder(this).setTitle(title)
            .setItems(labels, (dialog, which) -> {
                if (which < seconds.length) startCapture(mode, frequency, address, Integer.toString(seconds[which]));
                else if (which == seconds.length) enterDuration(mode, frequency, address);
                else startCapture(mode, frequency, address, "until-stopped");
            })
            .setNegativeButton("Cancel", null).show();
    }

    private void enterDuration(String mode, int frequency, String address) {
        int maxSeconds = MAX_CAPTURE_SECONDS;
        EditText input = new EditText(this);
        input.setSingleLine();
        input.setInputType(InputType.TYPE_CLASS_NUMBER);
        input.setHint("Seconds");
        LinearLayout box = column();
        box.setPadding(dp(24), 0, dp(24), 0);
        box.addView(input);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Custom duration")
            .setMessage("Enter 1–" + maxSeconds + " seconds. Android Wi-Fi pauses until the session ends.")
            .setView(box).setNegativeButton("Cancel", null).setPositiveButton("Start", null).create();
        dialog.setOnShowListener(unused -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            int seconds;
            try {
                seconds = Integer.parseInt(input.getText().toString());
            } catch (NumberFormatException error) {
                seconds = 0;
            }
            if (seconds < 1 || seconds > maxSeconds) {
                input.setError("Enter 1–" + maxSeconds + " seconds.");
                return;
            }
            dialog.dismiss();
            startCapture(mode, frequency, address, Integer.toString(seconds));
        }));
        dialog.show();
    }

    private void startCapture(String mode, int frequency, String address, String duration) {
        if (mode.equals("wifite")) {
            startWifite(frequency, duration, address);
            return;
        }
        String options = frequency + " " + duration;
        if (mode.equals("wifi") && !address.isEmpty()) mode = "wifi-ap";
        String command = mode + " " + options + (address.isEmpty() ? "" : " " + address);
        action(command, "Starting Wi-Fi capture…");
    }

    private static final String CAPTURE_NAME = "(wifi|lab|survey)-[0-9]{8}-[0-9]{6}-[0-9]+\\.pcap";

    private void pickCapture(String analyzer) {
        if (!authenticated || runningCommand || active) {
            new AlertDialog.Builder(this).setMessage("Finish the current session before opening a capture.")
                .setPositiveButton("OK", null).show();
            return;
        }
        commands.execute(() -> {
            Result listing = run("captures");
            List<String> files = new ArrayList<>();
            for (String line : listing.output.split("\n")) {
                if (line.matches(CAPTURE_NAME)) files.add(line);
            }
            main.post(() -> {
                if (!foreground) return;
                AlertDialog.Builder picker = new AlertDialog.Builder(this).setTitle("Choose a saved capture")
                    .setNegativeButton("Close", null);
                if (files.isEmpty()) picker.setMessage("No launcher captures in Downloads/NetHunter.");
                else picker.setItems(files.toArray(new String[0]), (dialog, which) -> {
                    String file = files.get(which);
                    if (analyzer.startsWith("kismet")) {
                        openKismetWhenReady = true;
                        action("kismet " + file + (analyzer.equals("kismet-until-stopped") ? " until-stopped" : ""),
                            "Starting local Kismet replay…");
                    } else {
                        analyzeCapture(file, analyzer);
                    }
                });
                picker.show();
            });
        });
    }

    private void analyzeCapture(String name, String analyzer) {
        runningCommand = true;
        main.removeCallbacks(refresh);
        statusText.setText("Reading " + name + "…");
        updateButtons();
        commands.execute(() -> {
            Result result = run("analyze " + name + " " + analyzer);
            String output = result.output.replaceAll("(?m)^(?:\\[!\\] Checking chroot environment\\.|Linux|\\[\\+\\] .* (?:was mounted|has been started) already\\.)\\n?", "").trim();
            main.post(() -> {
                runningCommand = false;
                updateButtons();
                if (foreground) {
                    String title = analyzer.equals("wash") ? "Wash · offline WPS"
                        : analyzer.equals("hcx") ? "hcxtools · capture details" : "Capture summary";
                    ScrollView scroll = new ScrollView(this);
                    TextView report = label(output.isEmpty() ? "No output." : output, 14, INK, false);
                    report.setPadding(dp(24), dp(10), dp(24), dp(10));
                    report.setTextIsSelectable(true);
                    scroll.addView(report);
                    new AlertDialog.Builder(this).setTitle(result.code == 0 ? title : "Could not read capture")
                        .setView(scroll).setPositiveButton("Close", null).show();
                }
                readStatus();
            });
        });
    }

    private void showWirelessTools() {
        String[] tools = {"TShark · capture summary", "Wash · offline WPS check", "hcxtools · capture details",
            "Aircrack-ng", "Aireplay-ng", "Wifite", "Kismet · replay capture", "Reaver", "Wireshark · KeX", "Open NetHunter Terminal"};
        String[] details = {
            "Aircrack-ng is installed in Kali. It reads saved captures for credential audits. Open NetHunter Terminal and choose Kali. Captures are in /sdcard/Download/NetHunter.",
            "Aireplay-ng is installed in Kali. Use it from NetHunter Terminal with a separately prepared lab monitor session. It can transmit; the launcher capture modes are receive-only.",
            "",
            "",
            "Reaver is installed in Kali for active WPS testing. Use Wash to check a capture for WPS first. Reaver is kept in NetHunter Terminal for authorized lab use.",
            "Start the Kali desktop in NetHunter KeX, then open Wireshark and select a file from /sdcard/Download/NetHunter. KeX runs on this phone."
        };
        new AlertDialog.Builder(this).setTitle("Wireless tools")
            .setItems(tools, (dialog, which) -> {
                switch (which) {
                    case 0: pickCapture("summary"); break;
                    case 1: pickCapture("wash"); break;
                    case 2: pickCapture("hcx"); break;
                    case 5:
                        if (canStartWifite()) {
                            new AlertDialog.Builder(this).setTitle("Wifite")
                                .setMessage("Discovery listens on a channel. Active audit listens and transmits on a selected access point. Android Wi-Fi pauses during either session.")
                                .setPositiveButton("Choose channel", (info, button) -> pickBand("wifite"))
                                .setNeutralButton("Active audit", (info, button) -> pickScanBand(true))
                                .setNegativeButton("Cancel", null).show();
                        }
                        break;
                    case 6:
                        if (statusText.getText().toString().startsWith("Kismet replay ready")) {
                            openKismet();
                        } else {
                            new AlertDialog.Builder(this).setTitle("Kismet · replay capture")
                                .setMessage("Review a saved capture in your phone’s browser. Kismet will ask you to create a login the first time. Use Restore normal mode to close the server.")
                                .setPositiveButton("Until stopped", (info, button) -> pickCapture("kismet-until-stopped"))
                                .setNeutralButton("15 minutes", (info, button) -> pickCapture("kismet"))
                                .setNegativeButton("Cancel", null).show();
                        }
                        break;
                    case 9: openPackage("com.offsec.nhterm", "NetHunter Terminal"); break;
                    default:
                        new AlertDialog.Builder(this).setTitle(tools[which]).setMessage(details[which - 3])
                            .setPositiveButton(which == 8 ? "Open NetHunter" : "Open Terminal",
                                (info, button) -> {
                                    if (which == 8) openNetHunter();
                                    else openPackage("com.offsec.nhterm", "NetHunter Terminal");
                                }).setNegativeButton("Close", null).show();
                }
            }).setNegativeButton("Close", null).show();
    }

    private boolean canStartWifite() {
        if (authenticated && !runningCommand && !active) return true;
        new AlertDialog.Builder(this)
            .setMessage("Allow launcher root access and end any current session before starting Wifite.")
            .setPositiveButton("OK", null).show();
        return false;
    }

    private void confirmWifiteAudit(int frequency, String address, String name) {
        new AlertDialog.Builder(this).setTitle("Active Wifite audit")
            .setMessage(name + "\n" + channelLabel(frequency) + " · " + address
                + "\n\nWifite can transmit as soon as it finds this access point and may disconnect clients. Continue only for a network you’re authorized to test.")
            .setPositiveButton("Choose duration", (dialog, which) ->
                pickDuration("wifite", frequency, address, name))
            .setNegativeButton("Cancel", null).show();
    }

    private void startWifite(int frequency, String duration, String address) {
        if (!canStartWifite()) return;
        String terminal = "com.offsec.nhterm";
        Intent intent = new Intent("neoterm.action.remote.execute");
        intent.setClassName(terminal, terminal + ".ui.term.NeoTermRemoteInterface");
        String extra = "neoterm.extra.remote.execute.";
        intent.putExtra(extra + "executable", "/data/data/com.offsec.nhterm/files/usr/bin/android-su");
        intent.putExtra(extra + "command", CONTROLLER + " wifite-terminal " + frequency + " " + duration
            + (address.isEmpty() ? "" : " " + address));
        intent.putExtra(extra + "session", "new");
        intent.putExtra(extra + "foreground", true);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException | SecurityException error) {
            new AlertDialog.Builder(this)
                .setMessage("Install or update NetHunter Terminal to open Wifite from the launcher.")
                .setPositiveButton("OK", null).show();
        }
    }

    private void openKismet() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:12501/")));
        } catch (ActivityNotFoundException error) {
            new AlertDialog.Builder(this).setMessage("Open http://127.0.0.1:12501/ in your phone’s browser.")
                .setPositiveButton("OK", null).show();
        }
    }

    private void pickUsbHost() {
        String[] labels = {"Mac", "Linux", "Windows"};
        String[] targets = {"mac", "lnx", "win"};
        new AlertDialog.Builder(this).setTitle("Choose your USB test computer")
            .setItems(labels, (dialog, which) -> action("usb " + targets[which],
                "Enabling USB keyboard and mouse…"))
            .setNegativeButton("Cancel", null).show();
    }

    private void confirmUsbTest() {
        new AlertDialog.Builder(this).setTitle("Send a test key?")
            .setMessage("Focus a blank editor on your USB test computer. This sends one lowercase n.")
            .setPositiveButton("Send n", (dialog, which) -> action("usb-test", "Sending test key…"))
            .setNegativeButton("Cancel", null).show();
    }

    private void pickReceiver() {
        String saved = getPreferences(MODE_PRIVATE).getString("receiver", "");
        String[] choices = saved.isEmpty()
            ? new String[] {"Find nearby or paired devices", "Enter address"}
            : new String[] {"Find nearby or paired devices", "Enter address", "Use saved receiver · " + saved};
        new AlertDialog.Builder(this).setTitle("Bad Bluetooth receiver")
            .setItems(choices, (dialog, index) -> {
                if (index == 0) findReceivers();
                else if (index == 1) enterReceiver();
                else confirmReceiver("Saved receiver", saved);
            })
            .setNegativeButton("Cancel", null).show();
    }

    private void findReceivers() {
        String[] permissions = Build.VERSION.SDK_INT >= 31
            ? new String[] {Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.BLUETOOTH_SCAN}
            : new String[] {Manifest.permission.ACCESS_FINE_LOCATION};
        for (String permission : permissions) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(permissions, NEARBY_PERMISSION);
                return;
            }
        }
        BluetoothManager manager = getSystemService(BluetoothManager.class);
        BluetoothAdapter adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null) {
            enterReceiver();
        } else if (!adapter.isEnabled()) {
            startActivityForResult(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE), ENABLE_BLUETOOTH);
        } else {
            receiverPicker = new ReceiverPicker(this, adapter, this::confirmReceiver, this::enterReceiver);
            receiverPicker.show();
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode != NEARBY_PERMISSION || results.length == 0) return;
        for (int result : results) {
            if (result != PackageManager.PERMISSION_GRANTED) {
                enterReceiver();
                return;
            }
        }
        findReceivers();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == ENABLE_BLUETOOTH && resultCode == RESULT_OK) findReceivers();
    }

    private void confirmReceiver(String name, String address) {
        new AlertDialog.Builder(this).setTitle("Start Bad Bluetooth?")
            .setMessage(name + "\n" + address + "\n\nSelect a receiver you own or are authorized to test.")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Start", (dialog, which) -> startBluetooth(address)).show();
    }

    private void startBluetooth(String address) {
        String normalized = address.toUpperCase(Locale.ROOT);
        if (!normalized.matches("([0-9A-F]{2}:){5}[0-9A-F]{2}")) return;
        getPreferences(MODE_PRIVATE).edit().putString("receiver", normalized).apply();
        action("bluetooth " + normalized, "Starting the Bluetooth keyboard…");
    }

    private void enterReceiver() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        input.setHint("AA:BB:CC:DD:EE:FF");
        input.setText(getPreferences(MODE_PRIVATE).getString("receiver", ""));
        LinearLayout box = column();
        box.setPadding(dp(24), 0, dp(24), 0);
        box.addView(input);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Lab receiver")
            .setMessage("Enter the Bluetooth address shown by bluetoothctl show on your Kali laptop.")
            .setView(box).setNegativeButton("Cancel", null).setPositiveButton("Start", null).create();
        dialog.setOnShowListener(unused -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String address = input.getText().toString().trim().toUpperCase(Locale.ROOT);
            if (!address.matches("([0-9A-F]{2}:){5}[0-9A-F]{2}")) {
                input.setError("Use six pairs of hex digits separated by colons.");
                return;
            }
            dialog.dismiss();
            startBluetooth(address);
        }));
        dialog.show();
    }

    private void openNetHunter() {
        openPackage("com.offsec.nethunter", "NetHunter");
    }

    private void openPackage(String packageName, String label) {
        Intent intent = getPackageManager().getLaunchIntentForPackage(packageName);
        if (intent != null) {
            try {
                startActivity(intent);
                return;
            } catch (ActivityNotFoundException | SecurityException ignored) {
                // The companion may have been removed or disabled.
            }
        }
        new AlertDialog.Builder(this).setMessage(label + " could not be opened.")
            .setPositiveButton("OK", null).show();
    }

    private void showLog() {
        commands.execute(() -> {
            Result result = run("log");
            main.post(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    new AlertDialog.Builder(this).setTitle("Session log").setMessage(result.output)
                        .setPositiveButton("Close", null).show();
                }
            });
        });
    }

    private void readStatus() {
        main.removeCallbacks(refresh);
        if (!foreground || runningCommand) return;
        commands.execute(() -> {
            Result result = run("status");
            main.post(() -> {
                if (!foreground || runningCommand) return;
                authenticated = result.code == 0;
                if (authenticated) {
                    String[] lines = result.output.split("\n", 2);
                    usbActive = lines[0].equals("usb");
                    active = usbActive || lines[0].equals("active");
                    statusTitle.setText(active ? "Session active" : "Ready");
                    String message = lines.length == 2 ? lines[1] : "";
                    statusText.setText(message);
                    if (openKismetWhenReady && message.startsWith("Kismet replay ready")) {
                        openKismetWhenReady = false;
                        openKismet();
                    } else if (!active) {
                        openKismetWhenReady = false;
                    }
                    if (showScanWhenReady && !active) {
                        showScanWhenReady = false;
                        if (message.startsWith("Channel scan complete")) showScanResults(scanForWifite);
                    }
                } else {
                    statusTitle.setText("Root access needed");
                    statusText.setText("Allow NetHunter Launcher in Magisk. " + result.output);
                }
                updateButtons();
                main.postDelayed(refresh, authenticated ? 2000 : 5000);
            });
        });
    }

    private void action(String command, String progress) {
        runningCommand = true;
        main.removeCallbacks(refresh);
        statusText.setText(progress);
        updateButtons();
        commands.execute(() -> {
            Result result = run(command);
            main.post(() -> {
                runningCommand = false;
                updateButtons();
                if (foreground && result.code != 0) {
                    new AlertDialog.Builder(this).setTitle("Could not complete action")
                        .setMessage(result.output.isEmpty() ? "Open the session log for details." : result.output)
                        .setPositiveButton("OK", null).show();
                }
                readStatus();
            });
        });
    }

    private Result run(String command) {
        try {
            Process process = new ProcessBuilder("su", "-mm", "-c", CONTROLLER + " " + command)
                .redirectErrorStream(true).start();
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) output.append(line).append('\n');
            }
            return new Result(process.waitFor(), output.toString().trim());
        } catch (IOException error) {
            return new Result(1, error.getMessage());
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            return new Result(1, "Command interrupted.");
        }
    }

    private void updateButtons() {
        capture.setEnabled(authenticated && !runningCommand && !active);
        scan.setEnabled(authenticated && !runningCommand && !active);
        survey.setEnabled(authenticated && !runningCommand && !active);
        analyze.setEnabled(authenticated && !runningCommand && !active);
        bluetooth.setEnabled(authenticated && !runningCommand && !active);
        usb.setEnabled(authenticated && !runningCommand && !active);
        testKey.setVisibility(usbActive ? View.VISIBLE : View.GONE);
        testKey.setEnabled(authenticated && !runningCommand);
        restore.setEnabled(authenticated && !runningCommand);
    }

    private Button button(String name, int background, int foreground, int stroke, Runnable click) {
        Button button = new Button(this);
        button.setText(name);
        button.setAllCaps(false);
        button.setTextSize(16);
        button.setTextColor(new ColorStateList(new int[][] {{-android.R.attr.state_enabled}, {}},
            new int[] {0xff73817a, foreground}));
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3370837a),
            shape(background, stroke, 13), null));
        button.setPadding(dp(12), 0, dp(12), 0);
        button.setMinHeight(dp(52));
        button.setOnClickListener(view -> click.run());
        return button;
    }

    private TextView label(String text, int size, int color, boolean bold) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(size);
        label.setTextColor(color);
        if (bold) label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return label;
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private void add(LinearLayout layout, View child, int margin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(margin);
        layout.addView(child, params);
    }

    private GradientDrawable shape(int color, int stroke, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setStroke(dp(1), stroke);
        shape.setCornerRadius(dp(radius));
        return shape;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static final class Result {
        final int code;
        final String output;

        Result(int code, String output) {
            this.code = code;
            this.output = output;
        }
    }
}

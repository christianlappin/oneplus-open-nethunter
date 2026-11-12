package com.oneplusopen.nhlauncher;

import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;
import java.util.function.BiConsumer;

final class ReceiverPicker {
    private final Activity activity;
    private final BluetoothAdapter bluetooth;
    private final BiConsumer<String, String> select;
    private final Runnable manual;
    private final List<String> addresses = new ArrayList<>();
    private final ArrayAdapter<String> rows;
    private TextView hint;
    private AlertDialog dialog;
    private boolean registered;

    private final BroadcastReceiver events = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (BluetoothDevice.ACTION_FOUND.equals(intent.getAction())) {
                BluetoothDevice device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
                if (device != null && device.getType() != BluetoothDevice.DEVICE_TYPE_LE) add(device);
            } else if (BluetoothAdapter.ACTION_DISCOVERY_FINISHED.equals(intent.getAction())) {
                hint.setText("Scan finished. Select a receiver or tap Scan again.");
            }
        }
    };

    ReceiverPicker(Activity activity, BluetoothAdapter bluetooth, BiConsumer<String, String> select, Runnable manual) {
        this.activity = activity;
        this.bluetooth = bluetooth;
        this.select = select;
        this.manual = manual;
        rows = new ArrayAdapter<>(activity, android.R.layout.simple_list_item_1);
    }

    void show() {
        LinearLayout layout = new LinearLayout(activity);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * activity.getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding / 2, padding, 0);
        hint = new TextView(activity);
        hint.setText("Put your receiver in discoverable mode.");
        layout.addView(hint);
        ListView list = new ListView(activity);
        list.setAdapter(rows);
        int height = Math.min(activity.getResources().getDisplayMetrics().heightPixels / 3, padding * 11);
        layout.addView(list, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height));
        list.setOnItemClickListener((parent, view, position, id) -> {
            String address = addresses.get(position);
            String row = rows.getItem(position);
            close();
            select.accept(row.substring(0, row.indexOf('\n')), address);
        });
        dialog = new AlertDialog.Builder(activity).setTitle("Select your receiver")
            .setView(layout).setNegativeButton("Cancel", null)
            .setNeutralButton("Enter address", (unused, which) -> {
                close();
                manual.run();
            })
            .setPositiveButton("Scan again", null).create();
        dialog.setOnDismissListener(unused -> stopDiscovery());
        dialog.show();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(unused -> scan());
        try {
            for (BluetoothDevice device : bluetooth.getBondedDevices()) {
                if (device.getType() != BluetoothDevice.DEVICE_TYPE_LE) add(device);
            }
            IntentFilter filter = new IntentFilter(BluetoothDevice.ACTION_FOUND);
            filter.addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED);
            if (Build.VERSION.SDK_INT >= 33) activity.registerReceiver(events, filter, Context.RECEIVER_EXPORTED);
            else activity.registerReceiver(events, filter);
            registered = true;
            scan();
        } catch (SecurityException error) {
            hint.setText("Nearby Devices permission is required to scan.");
        }
    }

    void close() {
        if (dialog != null) dialog.dismiss();
    }

    private void add(BluetoothDevice device) {
        String address = device.getAddress();
        if (addresses.contains(address)) return;
        String name = device.getName();
        addresses.add(address);
        rows.add((name == null || name.isEmpty() ? "Unnamed device" : name.replace('\n', ' '))
            + "\n" + address + (device.getBondState() == BluetoothDevice.BOND_BONDED ? " · paired" : ""));
    }

    private void scan() {
        try {
            if (bluetooth.isDiscovering() || bluetooth.startDiscovery()) {
                hint.setText("Scanning. Make sure your receiver is discoverable.");
            } else {
                hint.setText("Scan could not start. Select a paired device or enter its address.");
            }
        } catch (SecurityException error) {
            hint.setText("Nearby Devices permission is required to scan.");
        }
    }

    private void stopDiscovery() {
        if (!registered) return;
        activity.unregisterReceiver(events);
        registered = false;
        try {
            bluetooth.cancelDiscovery();
        } catch (SecurityException ignored) {
            // Permission can be revoked while this dialog is open.
        }
    }
}

#!/bin/sh
set -eu
cd /root/badbt
peer=$1
policy=/etc/dbus-1/system.d/org.thanhle.btkbservice.conf
test ! -e "$policy"
if service dbus status >/dev/null 2>&1 || service bluetooth status >/dev/null 2>&1; then
    echo 'Stop the existing Kali Bluetooth and D-Bus services before starting BadBluetooth.' >&2
    exit 1
fi
work=$(mktemp -d)
remove_bond=0
cleanup() {
    if [ "$remove_bond" = 1 ]; then
        timeout 4 bluetoothctl remove "$peer" >/dev/null 2>&1 || true
    fi
    if [ -n "${agent:-}" ]; then kill "$agent" 2>/dev/null || true; fi
    if [ -n "${agent_input:-}" ]; then kill "$agent_input" 2>/dev/null || true; fi
    if [ -n "${daemon:-}" ]; then
        kill "$daemon" 2>/dev/null || true
        wait "$daemon" 2>/dev/null || true
    fi
    service dbus stop >/dev/null 2>&1 || true
    rm -f "$policy"
    rm -rf "$work"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
install -m 0644 org.thanhle.btkbservice.conf "$policy"
service dbus start
hciconfig hci0 up
bluetoothd --nodetach --noplugin=input,a2dp,avrcp,network --configfile=bluez-bredr.conf >"$work/bluez.log" 2>&1 &
daemon=$!
for attempt in $(seq 1 10); do
    if timeout 2 bluetoothctl show | grep -q 'Powered: yes'; then break; fi
    sleep 1
done
if ! timeout 2 bluetoothctl info "$peer" | grep -q 'Bonded: yes'; then
    remove_bond=1
fi
mkfifo "$work/agent-input"
{ printf '%s\n' default-agent 'pairable on'; sleep 260; } >"$work/agent-input" &
agent_input=$!
timeout 265 bluetoothctl --agent NoInputNoOutput <"$work/agent-input" >"$work/agent.log" 2>&1 &
agent=$!
NH_BADBT_PEER="$peer" timeout --signal=INT 250 python3 -u btk_server.py -n 'NH Lab Keyboard' -i hci0

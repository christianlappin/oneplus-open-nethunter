#!/bin/sh
set -eu
cd /root/badbt
peer=$1
mode=${2:-cli}
case "$mode" in cli|app) ;; *) exit 2;; esac
app_peer=/root/badbt/.app-peer
test ! -e "$app_peer"
policy=/etc/dbus-1/system.d/org.thanhle.btkbservice.conf
test ! -e "$policy"
if service dbus status >/dev/null 2>&1 || service bluetooth status >/dev/null 2>&1; then
    echo 'Stop the existing Kali Bluetooth and D-Bus services before starting BadBluetooth.' >&2
    exit 1
fi
work=$(mktemp -d)
remove_bond=0
app_enabled=0
app_server_pids() {
    pgrep -f '^python3 /root/badbt/btk_server.py( |$)' || true
}
cleanup() {
    if [ "$app_enabled" = 1 ]; then
        rm -f "$app_peer"
        for server in $(app_server_pids); do kill "$server" 2>/dev/null || true; done
    fi
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
{ printf '%s\n' default-agent 'pairable on'; sleep 460; } >"$work/agent-input" &
agent_input=$!
timeout 465 bluetoothctl --agent NoInputNoOutput <"$work/agent-input" >"$work/agent.log" 2>&1 &
agent=$!
if [ "$mode" = cli ]; then
    NH_BADBT_PEER="$peer" timeout --signal=INT 250 python3 -u btk_server.py -n 'NH Lab Keyboard' -i hci0
    exit $?
fi
app_enabled=1
(umask 077; printf '%s\n' "$peer" > "$app_peer")
echo 'BadBluetooth app ready. Open Bluetooth Arsenal and tap Start within 120 seconds.'
for attempt in $(seq 1 120); do
    [ -z "$(app_server_pids)" ] || break
    sleep 1
done
test -n "$(app_server_pids)" || exit 124
for attempt in $(seq 1 300); do
    [ -n "$(app_server_pids)" ] || exit 0
    sleep 1
done

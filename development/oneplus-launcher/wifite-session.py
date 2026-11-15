"""Run Wifite in the terminal and reap its capture and audit helpers."""

import ctypes
import os
from pathlib import Path
import re
import signal
import shutil
import struct
import subprocess
import sys
import time


def children():
    parent = str(os.getpid())
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            ppid = (entry / "stat").read_text().rsplit(")", 1)[1].split()[1]
        except (OSError, IndexError):
            continue
        if ppid == parent:
            result.append(int(entry.name))
    return result


def stop_children(process, terminal_interrupt=False):
    # Keep polling the direct children as descendants are reparented to us.
    # Reap Wifite through Popen so its exit status stays available.
    # Wifite treats a second SIGINT during cleanup as an emergency exit.
    # Let its two cleanup joins finish before escalating.
    for sig, grace in ((signal.SIGINT, 5.5), (signal.SIGTERM, 0.4), (signal.SIGKILL, 0.6)):
        signaled = {process.pid} if terminal_interrupt and sig == signal.SIGINT else set()
        end = time.monotonic() + grace
        while time.monotonic() < end:
            process.poll()
            for pid in children():
                if pid != process.pid:
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            live = set(children())
            if not live:
                return
            for pid in live - signaled:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
            signaled.update(live)
            time.sleep(0.05)


def snapshot_pcap(source, destination):
    """Copy complete records from the live classic PCAP Wifite just snapshotted."""
    with source.open("rb") as reader, destination.open("wb") as writer:
        header = reader.read(24)
        order = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
                 b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">"}
        if len(header) != 24 or header[:4] not in order:
            return False
        endian = order[header[:4]]
        snaplen = struct.unpack_from(endian + "I", header, 16)[0]
        writer.write(header)
        while record := reader.read(16):
            if len(record) != 16:
                break
            size = struct.unpack_from(endian + "I", record, 8)[0]
            if size > min(snaplen, 262144):
                return False
            payload = reader.read(size)
            if len(payload) != size:
                break
            writer.write(record)
            writer.write(payload)
    return True


def complete_handshake_peer(lines, bssid, client):
    progress = {}
    for line in lines:
        fields = line.lower().split("\t")
        if len(fields) != 4 or not fields[3].isdecimal():
            continue
        sender, receiver, number, counter = fields
        if number in ("1", "3") and sender == bssid:
            peer = receiver
        elif number in ("2", "4") and receiver == bssid:
            peer = sender
        else:
            continue
        if (peer in (bssid, "00:00:00:00:00:00") or (client is not None and peer != client)
                or not re.fullmatch(r"[0-9a-f][02468ace](?::[0-9a-f]{2}){5}", peer)):
            continue
        counter = int(counter)
        expected, replay = progress.get(peer, (1, 0))
        if number == "1":
            progress[peer] = (2, counter)
        elif number == str(expected) and (counter > replay if expected == 3 else counter == replay):
            if expected == 4:
                return peer
            progress[peer] = (expected + 1, counter)
    return None


def select_handshake(capfile, bssid, client):
    source = Path(capfile)
    clean = source.with_name(source.name + ".clean")
    scoped = source.with_name(source.name + ".scoped")
    try:
        if not snapshot_pcap(source, clean):
            return False
        tshark = ["tshark", "-n", "-r", str(clean)]
        result = subprocess.run(tshark + [
            "-Y", f"wlan.bssid == {bssid} && eapol", "-T", "fields", "-E", "occurrence=f",
            "-e", "wlan.sa", "-e", "wlan.da",
            "-e", "wlan_rsna_eapol.keydes.msgnr", "-e", "eapol.keydes.replay_counter",
        ], capture_output=True, text=True, timeout=8, check=True)
        peer = complete_handshake_peer(result.stdout.splitlines(), bssid, client)
        if peer is None:
            return False
        pair = (f"(wlan.sa == {bssid} && wlan.da == {peer}) || "
                f"(wlan.sa == {peer} && wlan.da == {bssid})")
        frames = f"wlan.bssid == {bssid} && (wlan.fc.type_subtype == 0x08 || (eapol && ({pair})))"
        subprocess.run(tshark + ["-Y", frames, "-F", "pcap", "-w", str(scoped)],
                       capture_output=True, timeout=8, check=True)
        scoped.replace(source)
        return True
    finally:
        clean.unlink(missing_ok=True)
        scoped.unlink(missing_ok=True)


def active_wifite(scope, args):
    # Wifite normally sends a broadcast burst as well as client-specific
    # bursts. Override only the WPA deauth step in this process.
    from wifite import wifite
    from wifite.config import Configuration

    sys.argv = ["wifite", *args]
    Configuration.initialize(load_interface=False)
    from wifite.attack.wpa import AttackWPA, Handshake
    from wifite.tools.aireplay import Aireplay

    bssid = args[args.index("--bssid") + 1].lower()
    client = None if scope == "whole-ap" else scope
    if not shutil.which("tshark"):
        raise RuntimeError("Install tshark before running the ALFA Active audit")
    sent = False

    def deauth(_attack, target):
        nonlocal sent
        if sent or target.bssid.lower() != bssid:
            return
        if client is not None and all(station.station.lower() != client for station in target.clients):
            return
        sent = True
        scope_label = f"directed deauth burst to {client}" if client else f"broadcast deauth burst for {bssid}"
        print(f"\nWifite: sending one {scope_label}", flush=True)
        Aireplay.deauth(bssid, client_mac=client, num_deauths=1, timeout=5)

    def has_handshake(handshake):
        return select_handshake(handshake.capfile, bssid, client)

    AttackWPA.deauth = deauth
    Handshake.has_handshake = has_handshake
    return wifite.main()


def discovery_wifite(args):
    from wifite import wifite
    from wifite.config import Configuration

    sys.argv = ["wifite", *args]
    Configuration.initialize(load_interface=False)
    from wifite.util.scanner import Scanner

    select_targets = Scanner.select_targets

    def select_discovered_targets(scanner):
        if scanner.target is None and not scanner.targets:
            print("\nNo access points found on this channel. Try another channel or let the scan run longer.",
                  flush=True)
            return []
        # NetHunter Terminal can deliver another Ctrl+C as input starts.
        # Keep the picker available and let launcher Stop terminate the session.
        previous_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            return select_targets(scanner)
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    Scanner.select_targets = select_discovered_targets
    return wifite.main()


def main():
    # Linux reparents orphaned helpers to this supervisor instead of PID 1.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not supervise Wifite child processes")

    duration = sys.argv[1]
    deadline = None if duration == "until-stopped" else time.monotonic() + int(duration)
    command = sys.argv[2:]
    discovery = command[0] == "--discovery"
    stopped = False
    terminal_interrupt = False

    def request_stop(sig, _frame):
        nonlocal stopped, terminal_interrupt
        # Wifite uses the terminal's SIGINT to advance to its numbered picker.
        if sig == signal.SIGINT:
            if discovery:
                return
            terminal_interrupt = True
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, request_stop)

    if discovery or command[0] == "--client":
        source = sys.orig_argv[sys.orig_argv.index("-c") + 1]
        tool_index = 1 if discovery else 2
        if command[tool_index] != "wifite":
            raise ValueError("This launcher mode requires Wifite")
        worker = ["--discovery-worker"] if discovery else ["--active-worker", command[1]]
        command = [sys.executable, "-c", source, *worker, *command[tool_index + 1:]]
    process = subprocess.Popen(command)
    try:
        while not stopped:
            code = process.poll()
            if code is not None:
                return 128 - code if code < 0 else code
            if deadline is not None and time.monotonic() >= deadline:
                return 124
            time.sleep(0.1)
        return 130
    finally:
        stop_children(process, terminal_interrupt)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--active-worker":
        sys.exit(active_wifite(sys.argv[2], sys.argv[3:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--discovery-worker":
        sys.exit(discovery_wifite(sys.argv[2:]))
    sys.exit(main())

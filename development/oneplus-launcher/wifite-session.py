"""Run Wifite in the terminal and reap its capture and audit helpers."""

import ctypes
import os
from pathlib import Path
import signal
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


def signal_children(sig):
    for pid in children():
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def stop_children(process):
    # Keep polling the direct children as descendants are reparented to us.
    # Reap Wifite through Popen so its exit status stays available.
    for sig, grace in ((signal.SIGINT, 0.6), (signal.SIGTERM, 0.4), (signal.SIGKILL, 0.6)):
        end = time.monotonic() + grace
        while time.monotonic() < end:
            process.poll()
            for pid in children():
                if pid != process.pid:
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            if not children():
                return
            signal_children(sig)
            time.sleep(0.05)


def main():
    # Linux reparents orphaned helpers to this supervisor instead of PID 1.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not supervise Wifite child processes")

    stopped = False

    def request_stop(_sig, _frame):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, request_stop)

    duration = sys.argv[1]
    deadline = None if duration == "until-stopped" else time.monotonic() + int(duration)
    process = subprocess.Popen(sys.argv[2:])
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
        stop_children(process)


if __name__ == "__main__":
    sys.exit(main())

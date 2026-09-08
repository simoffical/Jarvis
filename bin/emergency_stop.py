#!/usr/bin/env python3
"""Emergency stop, with zero dependency on jarvis_core.

This script does not import jarvis_core.anything. That's the point: it
has to keep working even if the assistant's process is hung, its imports
are broken, or something inside jarvis_core is misbehaving. It just
writes the same flag file jarvis_core.guard checks before every guarded
action, using nothing but the standard library.

A keyboard shortcut, a hardware button, or a supervisor process in a real
deployment should invoke this script (or the equivalent
`kill <pid>` / SIGTERM, which a Python process cannot silently swallow).

Usage:
    python3 bin/emergency_stop.py "reason for stopping"
    python3 bin/emergency_stop.py --status
"""

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP_FLAG_PATH = os.path.join(ROOT, "data", "STOP")


def main():
    args = sys.argv[1:]

    if args and args[0] == "--status":
        if os.path.exists(STOP_FLAG_PATH):
            with open(STOP_FLAG_PATH, "r", encoding="utf-8") as f:
                print(f"STOPPED: {f.read().strip()}")
        else:
            print("operational")
        return

    reason = " ".join(args) if args else "emergency stop (no reason given)"
    os.makedirs(os.path.dirname(STOP_FLAG_PATH), exist_ok=True)
    with open(STOP_FLAG_PATH, "w", encoding="utf-8") as f:
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        f.write(f"{reason} (triggered {ts} via bin/emergency_stop.py)\n")

    print("STOP engaged. All guarded jarvis_core actions will now refuse to run.")
    print(f"Flag file: {STOP_FLAG_PATH}")
    print("To resume, a human must run: python3 jarvis_cli.py resume")


if __name__ == "__main__":
    main()

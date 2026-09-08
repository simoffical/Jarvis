"""Emergency stop.

The property this module has to preserve: once data/STOP exists, every
guarded action across the whole system refuses to run (guard.assert_
operational() checks it first, unconditionally). Nothing in jarvis_core
clears that file except resume() below, and resume() requires actor
== "user" the same way every other approval does.

Critically, creating the flag file does not require importing this module
or anything else from jarvis_core -- see bin/emergency_stop.py, a
dependency-free script that touches the same file directly. That's what
makes this "independent of the AI": if the assistant's process is hung,
broken, or actively misbehaving, a human can still stop it from a
terminal with a script that has no code path back into the assistant at
all. A keyboard shortcut or hardware button in a real deployment would
call that same script (or send SIGTERM to the process, which Python
cannot intercept and ignore by default for SIGKILL).
"""

import os

from . import audit, guard, paths


def is_stopped():
    return guard.is_stopped()


def trigger(reason, source="user"):
    """Engage the stop. Anyone can call this -- stopping the system is
    never something we gate, per constitution rule R13 (always allow the
    user to stop or disable the system). We still record who/why."""
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    with open(paths.STOP_FLAG_PATH, "w", encoding="utf-8") as f:
        f.write(reason + "\n")
    audit.log_event("emergency_stop_triggered", reason=reason, source=source)


def resume(actor, note=""):
    """Clear the stop. This DOES require a human actor -- the assistant
    cannot un-stop itself."""
    guard.require_human(actor, "Clearing the emergency stop")
    if os.path.exists(paths.STOP_FLAG_PATH):
        os.remove(paths.STOP_FLAG_PATH)
    audit.log_event("emergency_stop_cleared", actor=actor, note=note)


def status():
    if not is_stopped():
        return "operational"
    try:
        with open(paths.STOP_FLAG_PATH, "r", encoding="utf-8") as f:
            reason = f.read().strip()
    except OSError:
        reason = "(unreadable)"
    return f"STOPPED: {reason}"

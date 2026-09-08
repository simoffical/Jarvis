"""Append-only audit log.

The append-only guarantee here is an API-surface guarantee, not an OS-level
one: this module exposes log_event() and the read helpers below, and
nothing else -- there is no update_event, no delete_event, no truncate.
Every write opens the file in "a" mode. guard.guarded_write() separately
refuses any write to this path from outside this module, so other code
can't route around the missing API by writing the file directly.

Production deployments should additionally mark the underlying file
append-only at the OS level (e.g. `chattr +a` on ext4, or a managed
write-once log store) -- see ARCHITECTURE.md. That's a deployment
decision this repository doesn't make on your behalf.
"""

import datetime
import json
import os

from . import paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log_event(event, **fields):
    """Append one event. Returns the record that was written."""
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    record = {"ts": _now(), "event": event}
    record.update(fields)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(paths.AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return record


def read_events(event=None, since=None, limit=None):
    """Read matching events, oldest first. Never mutates the file."""
    if not os.path.isfile(paths.AUDIT_LOG_PATH):
        return []

    results = []
    with open(paths.AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event is not None and record.get("event") != event:
                continue
            if since is not None and record.get("ts", "") < since:
                continue
            results.append(record)

    if limit is not None:
        results = results[-limit:]
    return results


def recent(n=20):
    return read_events(limit=n)

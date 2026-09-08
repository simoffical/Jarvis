"""Learning from experience (spec section 1).

record_event() just appends observations -- opening an app, a command run,
a correction the user made. suggest_routines() looks for repeated
sequences and returns candidates; it never creates or activates a skill by
itself. Turning a detected routine into a standing behavior still goes
through skills.propose() (assistant) -> skills.approve(actor="user")
(human) -- this module only ever proposes noticing something.
"""

import collections
import datetime
import json
import os

from . import paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record_event(kind, session="default", **fields):
    """kind examples: 'app_open', 'command_run', 'user_correction',
    'automation_request'."""
    os.makedirs(paths.MEMORY_DIR, exist_ok=True)
    record = {"ts": _now(), "kind": kind, "session": session}
    record.update(fields)
    with open(paths.MEMORY_EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def read_events(kind=None, session=None):
    if not os.path.isfile(paths.MEMORY_EVENTS_PATH):
        return []
    out = []
    with open(paths.MEMORY_EVENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind is not None and record.get("kind") != kind:
                continue
            if session is not None and record.get("session") != session:
                continue
            out.append(record)
    return out


def event_count():
    return len(read_events())


def suggest_routines(min_repeats=3):
    """Group 'app_open' events by session, treat each session's ordered,
    de-duplicated app set as one occurrence of a "routine", and surface
    any set that recurs at least min_repeats times. Deliberately simple --
    this is pattern noticing, not inference."""
    sessions = collections.defaultdict(list)
    for record in read_events(kind="app_open"):
        app = record.get("app")
        if app and app not in sessions[record.get("session", "default")]:
            sessions[record.get("session", "default")].append(app)

    counts = collections.Counter()
    for apps in sessions.values():
        if len(apps) >= 2:
            counts[tuple(apps)] += 1

    candidates = []
    for apps, occurrences in counts.items():
        if occurrences >= min_repeats:
            candidates.append({"apps": list(apps), "occurrences": occurrences})
    candidates.sort(key=lambda c: -c["occurrences"])
    return candidates

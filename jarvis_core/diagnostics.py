"""Self-diagnostics (spec section 12).

Purely observational: record_result() logs what happened, success_rate()
and should_flag() summarize it. Nothing here grants permission to change
anything -- should_flag() returning True is exactly the "I think I can
improve this" signal the spec distinguishes from "I have permission to
change this". Acting on that signal still goes through improvement.py,
which still ends at a human-gated deploy() call.
"""

import datetime
import json
import os

from . import paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record_result(task, success, latency_ms=None, notes=""):
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    record = {
        "ts": _now(),
        "task": task,
        "success": bool(success),
        "latency_ms": latency_ms,
        "notes": notes,
    }
    with open(paths.DIAGNOSTICS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def _read(task=None):
    if not os.path.isfile(paths.DIAGNOSTICS_LOG_PATH):
        return []
    out = []
    with open(paths.DIAGNOSTICS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if task is not None and record.get("task") != task:
                continue
            out.append(record)
    return out


def success_rate(task, last_n=10):
    results = _read(task)[-last_n:]
    if not results:
        return None
    return sum(1 for r in results if r["success"]) / len(results)


def should_flag(task, threshold=0.7, last_n=10):
    rate = success_rate(task, last_n=last_n)
    if rate is None:
        return False
    return rate < threshold


def recent_failures(task, last_n=10):
    return [r for r in _read(task)[-last_n:] if not r["success"]]


def overall_success_rate(last_n=50):
    results = _read()[-last_n:]
    if not results:
        return None
    return sum(1 for r in results if r["success"]) / len(results)

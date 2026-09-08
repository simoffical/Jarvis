"""Configurable autonomy levels (spec section 14).

There is deliberately no level above 5, and no code path that sets a
level other than set_level() below, which requires actor == "user".
Nothing in jarvis_core raises its own autonomy -- proposals from the
improvement loop or proactive suggestions can *recommend* a level change,
but only a human calling set_level(..., actor="user") -- via the CLI --
actually changes it.
"""

import datetime
import enum
import json
import os

from . import audit, guard, paths


class AutonomyLevel(enum.IntEnum):
    CONVERSATION_ONLY = 0
    INFORMATION_RETRIEVAL = 1
    SAFE_AUTOMATION = 2
    MULTISTEP_WITH_CONFIRMATION = 3
    PROACTIVE_APPROVED_WORKFLOWS = 4
    SANDBOX_EXPERIMENTATION = 5


DESCRIPTIONS = {
    AutonomyLevel.CONVERSATION_ONLY: "Conversation only.",
    AutonomyLevel.INFORMATION_RETRIEVAL: "Conversation + information retrieval.",
    AutonomyLevel.SAFE_AUTOMATION: "Safe computer automation.",
    AutonomyLevel.MULTISTEP_WITH_CONFIRMATION: "Multi-step automation with confirmation.",
    AutonomyLevel.PROACTIVE_APPROVED_WORKFLOWS: "Proactive assistance + approved workflows.",
    AutonomyLevel.SANDBOX_EXPERIMENTATION: "Experimental sandbox learning.",
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _default_state():
    return {"level": int(AutonomyLevel.CONVERSATION_ONLY), "history": []}


def _load():
    if not os.path.isfile(paths.AUTONOMY_PATH):
        return _default_state()
    try:
        with open(paths.AUTONOMY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_state()


def get_level():
    return AutonomyLevel(_load()["level"])


def get_history():
    return list(_load()["history"])


def set_level(level, actor, reason=""):
    """Change the autonomy level. Human-only, and blocked by the
    emergency stop like every other guarded action -- resume() is the
    one and only way out of a stop, with no side doors for "just
    lowering the level"."""
    guard.assert_operational()
    guard.require_human(actor, "Changing the autonomy level")

    level = AutonomyLevel(level)
    state = _load()
    old_level = state["level"]
    state["level"] = int(level)
    state["history"].append(
        {"ts": _now(), "from": old_level, "to": int(level), "actor": actor, "reason": reason}
    )
    guard.guarded_write(paths.AUTONOMY_PATH, json.dumps(state, indent=2))
    audit.log_event(
        "autonomy_level_changed", from_level=old_level, to_level=int(level), actor=actor, reason=reason
    )
    return level

"""Versioned personality (spec section 5).

commit() requires actor == "user" -- the assistant can propose() a new
profile (e.g. after noticing the user always asks for shorter answers)
but a human has to accept it before it becomes current. The full history
is kept so revert_to() can restore any earlier version.

This module must never be used to talk the user into changing a setting;
it stores what's chosen, it doesn't lobby for a choice. Enforcing that
is a prompting/behavior concern outside what code can check, so it's
called out here instead: no persuasion copy lives in this file, and none
should be added to it.
"""

import dataclasses
import datetime
import json
import os

from . import audit, guard, paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclasses.dataclass
class PersonalityProfile:
    version: str
    formality: str
    verbosity: str
    humor_style: str
    sarcasm_level: int  # 0 = fully professional .. 5 = ruthlessly deadpan
    terms_of_address: str
    notes: str = ""
    created_at: str = dataclasses.field(default_factory=_now)

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


DEFAULT_PROFILE = PersonalityProfile(
    version="1.0",
    formality="high; formal address (e.g. 'sir'), never casual",
    verbosity="concise by default",
    humor_style="dry, deadpan understatement; sarcasm from wording, not delivery",
    sarcasm_level=4,
    terms_of_address="sir",
    notes=(
        "Sarcasm steps aside immediately for anything serious, technical, "
        "or urgent -- no joke lands ahead of a real problem being solved. "
        "Roughly one sarcastic observation per few interactions, not one "
        "per response."
    ),
)


def _default_state():
    return {"current": DEFAULT_PROFILE.to_dict(), "history": [], "pending": None}


def _load():
    if not os.path.isfile(paths.PERSONALITY_PATH):
        return _default_state()
    try:
        with open(paths.PERSONALITY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_state()


def _save(state):
    guard.guarded_write(paths.PERSONALITY_PATH, json.dumps(state, indent=2))


def current():
    return PersonalityProfile.from_dict(_load()["current"])


def history():
    return list(_load()["history"])


def propose(profile: PersonalityProfile, reason=""):
    """Assistant-callable. Stages a change; does not apply it."""
    guard.assert_operational()
    state = _load()
    state["pending"] = {"profile": profile.to_dict(), "reason": reason, "proposed_at": _now()}
    _save(state)
    audit.log_event("personality_change_proposed", version=profile.version, reason=reason)
    return profile


def commit(actor):
    """Human-only. Applies the currently pending proposal."""
    guard.assert_operational()
    guard.require_human(actor, "Committing a personality change")
    state = _load()
    pending = state.get("pending")
    if not pending:
        raise ValueError("No pending personality change to commit.")

    state["history"].append(state["current"])
    state["current"] = pending["profile"]
    state["pending"] = None
    _save(state)
    audit.log_event(
        "personality_committed", version=pending["profile"]["version"], actor=actor
    )
    return PersonalityProfile.from_dict(state["current"])


def revert_to(version, actor):
    guard.assert_operational()
    guard.require_human(actor, "Reverting the personality profile")
    state = _load()
    for i, snapshot in enumerate(state["history"]):
        if snapshot["version"] == version:
            state["history"].append(state["current"])
            state["current"] = snapshot
            del state["history"][i]
            _save(state)
            audit.log_event("personality_reverted", version=version, actor=actor)
            return PersonalityProfile.from_dict(state["current"])
    raise ValueError(f"No personality version {version!r} in history.")

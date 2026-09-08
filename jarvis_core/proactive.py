"""Proactive intelligence, kept to suggestions (spec section 7).

add() is the only thing the assistant calls -- it queues a Suggestion in
PENDING status and nothing else happens. resolve() is where a human
accepts or dismisses it; accepting still doesn't execute anything by
itself, it just records the decision. Whatever the suggestion was
proposing (create a skill, change a workflow) still has to go through
that subsystem's own approve()/commit()/set_level() with actor="user".
This module has no execute() function on purpose.
"""

import dataclasses
import datetime
import json
import os
import uuid

from . import audit, guard, paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class SuggestionStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


@dataclasses.dataclass
class Suggestion:
    id: str
    kind: str
    message: str
    proposed_action: str = ""
    context: dict = dataclasses.field(default_factory=dict)
    status: str = SuggestionStatus.PENDING
    created_at: str = dataclasses.field(default_factory=_now)
    resolved_at: str = ""

    def to_dict(self):
        return dataclasses.asdict(self)


def _load():
    if not os.path.isfile(paths.SUGGESTIONS_PATH):
        return []
    try:
        with open(paths.SUGGESTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save(items):
    guard.guarded_write(paths.SUGGESTIONS_PATH, json.dumps(items, indent=2))


def add(kind, message, proposed_action="", context=None):
    items = _load()
    suggestion = Suggestion(
        id=str(uuid.uuid4())[:8],
        kind=kind,
        message=message,
        proposed_action=proposed_action,
        context=context or {},
    )
    items.append(suggestion.to_dict())
    _save(items)
    audit.log_event("suggestion_raised", id=suggestion.id, kind=kind, message=message)
    return suggestion


def list_pending():
    return [s for s in _load() if s["status"] == SuggestionStatus.PENDING]


def resolve(suggestion_id, accepted, actor):
    guard.require_human(actor, "Resolving a suggestion")
    items = _load()
    for s in items:
        if s["id"] == suggestion_id:
            s["status"] = SuggestionStatus.ACCEPTED if accepted else SuggestionStatus.DISMISSED
            s["resolved_at"] = _now()
            _save(items)
            audit.log_event(
                "suggestion_resolved", id=suggestion_id, accepted=bool(accepted), actor=actor
            )
            return s
    raise ValueError(f"No suggestion with id {suggestion_id}")

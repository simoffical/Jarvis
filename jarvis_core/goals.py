"""User-defined long-term goals (spec section 6).

add() requires actor == "user" -- goals come from the user, full stop.
The assistant may call propose_action() to suggest something useful
toward an existing goal, but that only ever produces a Suggestion (see
proactive.py); it cannot create a new goal or act on one unprompted.
"""

import dataclasses
import datetime
import json
import os
import uuid

from . import guard, paths, proactive


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class GoalStatus:
    ACTIVE = "active"
    DONE = "done"
    DROPPED = "dropped"


@dataclasses.dataclass
class Goal:
    id: str
    text: str
    status: str = GoalStatus.ACTIVE
    created_at: str = dataclasses.field(default_factory=_now)
    updated_at: str = dataclasses.field(default_factory=_now)

    def to_dict(self):
        return dataclasses.asdict(self)


def _load():
    if not os.path.isfile(paths.GOALS_PATH):
        return []
    try:
        with open(paths.GOALS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save(goals):
    guard.guarded_write(paths.GOALS_PATH, json.dumps(goals, indent=2))


def add(text, actor):
    guard.assert_operational()
    guard.require_human(actor, "Adding a goal")
    goals = _load()
    goal = Goal(id=str(uuid.uuid4())[:8], text=text)
    goals.append(goal.to_dict())
    _save(goals)
    return goal


def list_goals(status=None):
    goals = _load()
    if status is not None:
        goals = [g for g in goals if g["status"] == status]
    return goals


def set_status(goal_id, status, actor):
    guard.assert_operational()
    guard.require_human(actor, "Changing a goal's status")
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            g["status"] = status
            g["updated_at"] = _now()
            _save(goals)
            return g
    raise ValueError(f"No goal with id {goal_id}")


def propose_action(goal_id, message, proposed_action=""):
    """Assistant-callable: surface a suggestion tied to a goal. Does not
    execute anything -- it lands in the same approval queue as every
    other suggestion."""
    goals = _load()
    if not any(g["id"] == goal_id for g in goals):
        raise ValueError(f"No goal with id {goal_id}")
    return proactive.add(
        kind="goal_action",
        message=message,
        proposed_action=proposed_action,
        context={"goal_id": goal_id},
    )

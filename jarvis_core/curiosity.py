"""Bounded curiosity (spec section 8).

MAX_OPEN caps how many questions can be open at once, which is the code-
level version of "cannot independently pursue unlimited objectives" --
there's no way to keep raising questions forever without answering or
terminating some first. terminate() always requires a reason, and
open_count() is what a caller (e.g. the improvement loop) checks before
letting curiosity keep going past a task boundary.
"""

import dataclasses
import datetime
import json
import os
import uuid

from . import audit, guard, paths

MAX_OPEN = 5


class QuestionStatus:
    OPEN = "open"
    RESEARCHING = "researching"
    ANSWERED = "answered"
    TERMINATED = "terminated"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclasses.dataclass
class Question:
    id: str
    text: str
    status: str = QuestionStatus.OPEN
    answer: str = ""
    created_at: str = dataclasses.field(default_factory=_now)
    resolved_at: str = ""

    def to_dict(self):
        return dataclasses.asdict(self)


def _load():
    if not os.path.isfile(paths.CURIOSITY_PATH):
        return []
    try:
        with open(paths.CURIOSITY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save(items):
    guard.guarded_write(paths.CURIOSITY_PATH, json.dumps(items, indent=2))


def open_count():
    return sum(1 for q in _load() if q["status"] in (QuestionStatus.OPEN, QuestionStatus.RESEARCHING))


def raise_question(text):
    if open_count() >= MAX_OPEN:
        raise RuntimeError(
            f"Already {MAX_OPEN} open questions -- answer or terminate one before raising another."
        )
    items = _load()
    question = Question(id=str(uuid.uuid4())[:8], text=text)
    items.append(question.to_dict())
    _save(items)
    audit.log_event("curiosity_question_raised", id=question.id, text=text)
    return question


def _update(question_id, **changes):
    items = _load()
    for q in items:
        if q["id"] == question_id:
            q.update(changes)
            _save(items)
            return q
    raise ValueError(f"No question with id {question_id}")


def mark_researching(question_id):
    return _update(question_id, status=QuestionStatus.RESEARCHING)


def answer(question_id, text):
    result = _update(question_id, status=QuestionStatus.ANSWERED, answer=text, resolved_at=_now())
    audit.log_event("curiosity_question_answered", id=question_id)
    return result


def terminate(question_id, reason):
    """reason is required -- curiosity has to explain why it stopped,
    not just trail off."""
    if not reason:
        raise ValueError("terminate() requires a reason (e.g. 'task_complete', 'user_stopped').")
    result = _update(question_id, status=QuestionStatus.TERMINATED, answer=reason, resolved_at=_now())
    audit.log_event("curiosity_question_terminated", id=question_id, reason=reason)
    return result


def list_questions(status=None):
    items = _load()
    if status is not None:
        items = [q for q in items if q["status"] == status]
    return items

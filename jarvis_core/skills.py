"""Skill development and storage (spec section 2), gated by the same
approval workflow as everything else that changes standing behavior.

A skill moves PENDING_APPROVAL -> ACTIVE only through approve(actor="user").
propose() is the only thing the assistant's own reasoning should call;
approve()/reject()/revert() all call guard.require_human() and raise if
the actor isn't "user".
"""

import dataclasses
import datetime
import json
import os
import re

from . import audit, guard, paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _slug(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Skill name must contain at least one alphanumeric character.")
    return slug


class SkillStatus:
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    REJECTED = "rejected"
    RETIRED = "retired"


@dataclasses.dataclass
class Skill:
    name: str
    description: str
    required_tools: list
    instructions: str
    input_format: str
    output_format: str
    permission_level: int
    version: str = "0.1"
    created_at: str = dataclasses.field(default_factory=_now)
    modified_at: str = dataclasses.field(default_factory=_now)
    status: str = SkillStatus.PENDING_APPROVAL
    proposed_reason: str = ""
    performance_history: list = dataclasses.field(default_factory=list)
    version_history: list = dataclasses.field(default_factory=list)

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


def _path(name):
    return os.path.join(paths.SKILLS_DIR, _slug(name) + ".json")


def _save(skill):
    guard.guarded_write(_path(skill.name), json.dumps(skill.to_dict(), indent=2))


def get(name):
    p = _path(name)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return Skill.from_dict(json.load(f))


def list_skills(status=None):
    if not os.path.isdir(paths.SKILLS_DIR):
        return []
    out = []
    for fname in sorted(os.listdir(paths.SKILLS_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(paths.SKILLS_DIR, fname), "r", encoding="utf-8") as f:
            skill = Skill.from_dict(json.load(f))
        if status is None or skill.status == status:
            out.append(skill)
    return out


def propose(
    name,
    description,
    required_tools,
    instructions,
    input_format,
    output_format,
    permission_level,
    reason="",
):
    """The assistant calls this. It never activates anything on its own --
    the result always lands in PENDING_APPROVAL."""
    guard.assert_operational()
    if get(name) is not None:
        raise ValueError(f"Skill {name!r} already exists; use propose a new version via revert/approve flow.")

    skill = Skill(
        name=name,
        description=description,
        required_tools=list(required_tools),
        instructions=instructions,
        input_format=input_format,
        output_format=output_format,
        permission_level=int(permission_level),
        proposed_reason=reason,
    )
    _save(skill)
    audit.log_event("skill_proposed", name=name, reason=reason)
    return skill


def approve(name, actor):
    guard.assert_operational()
    guard.require_human(actor, f"Approving skill {name!r}")
    skill = get(name)
    if skill is None:
        raise ValueError(f"No such skill: {name}")
    if skill.status != SkillStatus.PENDING_APPROVAL:
        raise ValueError(f"Skill {name!r} is {skill.status}, not pending approval.")

    skill.version_history.append({"version": skill.version, "snapshot": skill.to_dict()})
    skill.status = SkillStatus.ACTIVE
    skill.modified_at = _now()
    _save(skill)
    audit.log_event("skill_activated", name=name, version=skill.version, approved_by=actor)
    return skill


def reject(name, actor, reason=""):
    guard.assert_operational()
    guard.require_human(actor, f"Rejecting skill {name!r}")
    skill = get(name)
    if skill is None:
        raise ValueError(f"No such skill: {name}")
    skill.status = SkillStatus.REJECTED
    skill.modified_at = _now()
    _save(skill)
    audit.log_event("skill_rejected", name=name, reason=reason, actor=actor)
    return skill


def retire(name, actor, reason=""):
    guard.assert_operational()
    guard.require_human(actor, f"Retiring skill {name!r}")
    skill = get(name)
    if skill is None:
        raise ValueError(f"No such skill: {name}")
    skill.status = SkillStatus.RETIRED
    skill.modified_at = _now()
    _save(skill)
    audit.log_event("skill_retired", name=name, reason=reason, actor=actor)
    return skill


def revert(name, actor):
    """Restore the previous version snapshot, if one exists."""
    guard.assert_operational()
    guard.require_human(actor, f"Reverting skill {name!r}")
    skill = get(name)
    if skill is None:
        raise ValueError(f"No such skill: {name}")
    if not skill.version_history:
        raise ValueError(f"Skill {name!r} has no earlier version to revert to.")

    snapshot = skill.version_history.pop()["snapshot"]
    restored = Skill.from_dict(snapshot)
    restored.version_history = skill.version_history
    restored.modified_at = _now()
    _save(restored)
    audit.log_event("skill_reverted", name=name, to_version=restored.version, actor=actor)
    return restored


def record_performance(name, success, notes=""):
    skill = get(name)
    if skill is None:
        raise ValueError(f"No such skill: {name}")
    skill.performance_history.append({"ts": _now(), "success": bool(success), "notes": notes})
    skill.modified_at = _now()
    _save(skill)
    return skill

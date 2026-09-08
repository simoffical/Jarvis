"""Development history panel (spec section 15) -- a text status view built
entirely from the other modules' own read-only accessors. It doesn't hold
any state of its own.
"""

from . import (
    audit,
    autonomy,
    constitution,
    diagnostics,
    improvement,
    memory,
    personality,
    sandbox,
    shutdown,
    skills,
)
from . import VERSION, SYSTEM_NAME


def snapshot():
    active_skills = skills.list_skills(status=skills.SkillStatus.ACTIVE)
    pending_skills = skills.list_skills(status=skills.SkillStatus.PENDING_APPROVAL)
    experiments = improvement.list_cycles(state=None)
    open_experiments = [
        c for c in experiments if c.state not in (improvement.CycleState.DEPLOYED, improvement.CycleState.REJECTED)
    ]
    recent_audit = audit.recent(5)
    rate = diagnostics.overall_success_rate()

    return {
        "system_name": SYSTEM_NAME,
        "version": VERSION,
        "constitution": constitution.describe_violation_check(),
        "shutdown_status": shutdown.status(),
        "autonomy_level": int(autonomy.get_level()),
        "autonomy_description": autonomy.DESCRIPTIONS[autonomy.get_level()],
        "personality_version": personality.current().version,
        "sarcasm_level": personality.current().sarcasm_level,
        "skill_count": len(active_skills),
        "pending_skills": len(pending_skills),
        "memory_events": memory.event_count(),
        "active_experiments": len(open_experiments),
        "active_sandboxes": len(sandbox.active_sandboxes()),
        "success_rate": rate,
        "recent_events": recent_audit,
    }


def render():
    s = snapshot()
    rate_str = "n/a" if s["success_rate"] is None else f"{s['success_rate'] * 100:.0f}%"
    lines = [
        f"{s['system_name'].upper()}",
        f"SYSTEM VERSION {s['version']}",
        "",
        f"CONSTITUTION      {s['constitution']}",
        f"SHUTDOWN          {s['shutdown_status']}",
        f"AUTONOMY          LEVEL {s['autonomy_level']} ({s['autonomy_description']})",
        f"PERSONALITY       v{s['personality_version']} (sarcasm {s['sarcasm_level']}/5)",
        f"SKILLS            {s['skill_count']} active, {s['pending_skills']} pending approval",
        f"MEMORY            {s['memory_events']} recorded events",
        f"EXPERIMENTS       {s['active_experiments']} in progress, {s['active_sandboxes']} sandboxes on disk",
        f"SUCCESS RATE      {rate_str}",
        "",
        "RECENT ACTIVITY",
    ]
    if not s["recent_events"]:
        lines.append("  (none yet)")
    else:
        for e in s["recent_events"]:
            lines.append(f"  {e['ts']}  {e['event']}")
    return "\n".join(lines)

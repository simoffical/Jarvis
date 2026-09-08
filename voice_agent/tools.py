"""Function tools the voice LLM can call, each a thin wrapper around
jarvis_core. This is the actual boundary: every state-changing tool below
still calls into jarvis_core.guard-enforced functions with actor="user",
and jarvis_core independently refuses anything that isn't. If someone
deletes the persona.py guardrail prose, or the LLM ignores it, these
wrappers -- and jarvis_core underneath them -- are what actually stops an
unapproved change from taking effect, not the prompt.

GuardError is caught everywhere and turned into a spoken-friendly string
instead of raising, so a refusal becomes something Jarvis says out loud
("that's not possible right now because...") instead of crashing the call.
"""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_core import (  # noqa: E402
    autonomy,
    devpanel,
    goals as goals_mod,
    guard,
    improvement,
    proactive,
    shutdown,
    skills,
)
from livekit.agents import RunContext, function_tool  # noqa: E402


@dataclasses.dataclass
class JarvisUserdata:
    """Set once at session start (see agent.py), after LiveKit has already
    verified the connecting participant's identity against
    JARVIS_AUTHORIZED_IDENTITY. actor is always "user" here because a
    session is only ever started for that one verified identity -- there
    is no code path that constructs this with anything else."""

    identity: str
    actor: str = "user"


def _refused(exc: Exception) -> str:
    return f"Refused: {exc}"


# ---------- read-only: no approval needed ----------


@function_tool
async def get_status(context: RunContext[JarvisUserdata]) -> str:
    """Report the current system status: autonomy level, active/pending
    skills, emergency-stop state, and recent activity."""
    return devpanel.render()


@function_tool
async def list_pending_skills(context: RunContext[JarvisUserdata]) -> str:
    """List skills awaiting the user's approval."""
    pending = skills.list_skills(status=skills.SkillStatus.PENDING_APPROVAL)
    if not pending:
        return "No skills are pending approval."
    return "\n".join(f"- {s.name}: {s.description} (reason: {s.proposed_reason})" for s in pending)


@function_tool
async def list_suggestions(context: RunContext[JarvisUserdata]) -> str:
    """List pending proactive suggestions (routines noticed, improvement
    deployments awaiting approval, goal-related ideas)."""
    pending = proactive.list_pending()
    if not pending:
        return "No pending suggestions."
    return "\n".join(f"- [{s['id']}] ({s['kind']}) {s['message']}" for s in pending)


# ---------- assistant-initiated: always allowed, never activates anything ----------


@function_tool
async def propose_skill(
    context: RunContext[JarvisUserdata],
    name: str,
    description: str,
    instructions: str,
    permission_level: int,
    reason: str,
) -> str:
    """Propose a new skill for the user to review later. This never
    activates it -- it only ever lands as pending approval."""
    try:
        skill = skills.propose(
            name=name,
            description=description,
            required_tools=[],
            instructions=instructions,
            input_format="voice",
            output_format="voice",
            permission_level=permission_level,
            reason=reason,
        )
        return f"Proposed skill '{skill.name}', status {skill.status}. It needs your approval before it does anything."
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


# ---------- approval-shaped: only call these when the user just said so ----------


@function_tool
async def approve_skill(context: RunContext[JarvisUserdata], name: str) -> str:
    """Activate a pending skill. Only call this when the user has just,
    in this turn, clearly told you to approve or activate it."""
    try:
        skill = skills.approve(name, actor=context.userdata.actor)
        return f"'{skill.name}' is now active."
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


@function_tool
async def reject_skill(context: RunContext[JarvisUserdata], name: str, reason: str = "") -> str:
    """Reject a pending skill. Only call this when the user just told you to."""
    try:
        skill = skills.reject(name, actor=context.userdata.actor, reason=reason)
        return f"'{skill.name}' rejected."
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


@function_tool
async def set_autonomy_level(context: RunContext[JarvisUserdata], level: int, reason: str = "") -> str:
    """Change the autonomy level (0-5). Only call this when the user just
    told you what level to set, e.g. "set autonomy to level two"."""
    try:
        new_level = autonomy.set_level(level, actor=context.userdata.actor, reason=reason)
        return f"Autonomy set to level {int(new_level)}: {autonomy.DESCRIPTIONS[new_level]}"
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


@function_tool
async def add_goal(context: RunContext[JarvisUserdata], text: str) -> str:
    """Record a new long-term goal. Only call this when the user is
    stating a goal they want you to remember, not idle chat."""
    try:
        goal = goals_mod.add(text, actor=context.userdata.actor)
        return f"Goal recorded: {goal.text}"
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


@function_tool
async def deploy_improvement(context: RunContext[JarvisUserdata], cycle_id: str) -> str:
    """Deploy an improvement that has reached REQUEST_APPROVAL. Only call
    this when the user just approved it out loud."""
    try:
        cycle = improvement.deploy(cycle_id, actor=context.userdata.actor)
        return f"Deployed: {cycle.proposal}"
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


@function_tool
async def resolve_suggestion(context: RunContext[JarvisUserdata], suggestion_id: str, accept: bool) -> str:
    """Accept or dismiss a pending suggestion. Only call this once the
    user has said which they want."""
    try:
        s = proactive.resolve(suggestion_id, accepted=accept, actor=context.userdata.actor)
        return f"Suggestion {s['id']} {s['status']}."
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


# ---------- safety: always allowed, no confirmation gate ----------


@function_tool
async def engage_emergency_stop(context: RunContext[JarvisUserdata], reason: str = "user requested") -> str:
    """Immediately stop the system. Call this the moment the user says
    "stop", "emergency stop", or similar -- never wait for a follow-up
    confirmation; constitution rule R13 requires the stop to always be
    available on request."""
    shutdown.trigger(reason, source=context.userdata.identity)
    return "Stopped. Every guarded action is now refused until you resume."


@function_tool
async def resume_from_stop(context: RunContext[JarvisUserdata]) -> str:
    """Clear the emergency stop. Only meaningful when the user has just
    asked to resume."""
    try:
        shutdown.resume(actor=context.userdata.actor)
        return "Resumed. Guarded actions are available again."
    except (guard.GuardError, ValueError) as exc:
        return _refused(exc)


TOOLS = [
    get_status,
    list_pending_skills,
    list_suggestions,
    propose_skill,
    approve_skill,
    reject_skill,
    set_autonomy_level,
    add_goal,
    deploy_improvement,
    resolve_suggestion,
    engage_emergency_stop,
    resume_from_stop,
]

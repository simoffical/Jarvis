"""The self-improvement loop (spec section 3):

    OBSERVE -> ANALYZE -> IDENTIFY_PROBLEM -> PROPOSE_IMPROVEMENT ->
    TEST_SANDBOX -> EVALUATE -> REQUEST_APPROVAL -> DEPLOYED / REJECTED

Every transition is logged to the audit trail, so "what have you changed
recently / why did you change this" can be answered from data alone. The
only transition that changes real behavior is deploy(), and it enforces
two things: the cycle must already be sitting in REQUEST_APPROVAL (you
can't skip straight from PROPOSE_IMPROVEMENT to deployed), and the actor
must be "user". There is no silent-deploy path -- deploy() is the only
function that sets state to DEPLOYED, and it always requires a human.
"""

import dataclasses
import datetime
import json
import os
import uuid

from . import audit, guard, paths


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class CycleState:
    OBSERVE = "OBSERVE"
    ANALYZE = "ANALYZE"
    IDENTIFY_PROBLEM = "IDENTIFY_PROBLEM"
    PROPOSE_IMPROVEMENT = "PROPOSE_IMPROVEMENT"
    TEST_SANDBOX = "TEST_SANDBOX"
    EVALUATE = "EVALUATE"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    DEPLOYED = "DEPLOYED"
    REJECTED = "REJECTED"


_ORDER = [
    CycleState.OBSERVE,
    CycleState.ANALYZE,
    CycleState.IDENTIFY_PROBLEM,
    CycleState.PROPOSE_IMPROVEMENT,
    CycleState.TEST_SANDBOX,
    CycleState.EVALUATE,
    CycleState.REQUEST_APPROVAL,
]


@dataclasses.dataclass
class ImprovementCycle:
    id: str
    observation: str
    state: str = CycleState.OBSERVE
    analysis: str = ""
    problem: str = ""
    proposal: str = ""
    sandbox_result: str = ""
    evaluation: str = ""
    created_at: str = dataclasses.field(default_factory=_now)
    updated_at: str = dataclasses.field(default_factory=_now)
    decided_by: str = ""
    history: list = dataclasses.field(default_factory=list)

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


def _path(cycle_id):
    return os.path.join(paths.IMPROVEMENTS_DIR, cycle_id + ".json")


def _save(cycle):
    guard.guarded_write(_path(cycle.id), json.dumps(cycle.to_dict(), indent=2))


def get(cycle_id):
    p = _path(cycle_id)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return ImprovementCycle.from_dict(json.load(f))


def list_cycles(state=None):
    if not os.path.isdir(paths.IMPROVEMENTS_DIR):
        return []
    out = []
    for fname in sorted(os.listdir(paths.IMPROVEMENTS_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(paths.IMPROVEMENTS_DIR, fname), "r", encoding="utf-8") as f:
            cycle = ImprovementCycle.from_dict(json.load(f))
        if state is None or cycle.state == state:
            out.append(cycle)
    return out


def observe(observation):
    guard.assert_operational()
    cycle = ImprovementCycle(id=uuid.uuid4().hex[:8], observation=observation)
    cycle.history.append({"ts": _now(), "to": cycle.state})
    _save(cycle)
    audit.log_event("improvement_observed", id=cycle.id, observation=observation)
    return cycle


def _advance(cycle_id, expected_state, next_state, field_name, field_value):
    guard.assert_operational()
    cycle = get(cycle_id)
    if cycle is None:
        raise ValueError(f"No improvement cycle {cycle_id}")
    if cycle.state != expected_state:
        raise ValueError(f"Cycle {cycle_id} is in {cycle.state}, expected {expected_state}.")
    setattr(cycle, field_name, field_value)
    cycle.state = next_state
    cycle.updated_at = _now()
    cycle.history.append({"ts": cycle.updated_at, "to": next_state})
    _save(cycle)
    audit.log_event("improvement_advanced", id=cycle_id, to_state=next_state)
    return cycle


def analyze(cycle_id, analysis):
    return _advance(cycle_id, CycleState.OBSERVE, CycleState.ANALYZE, "analysis", analysis)


def identify_problem(cycle_id, problem):
    return _advance(cycle_id, CycleState.ANALYZE, CycleState.IDENTIFY_PROBLEM, "problem", problem)


def propose_improvement(cycle_id, proposal):
    return _advance(
        cycle_id, CycleState.IDENTIFY_PROBLEM, CycleState.PROPOSE_IMPROVEMENT, "proposal", proposal
    )


def record_sandbox_test(cycle_id, sandbox_result):
    return _advance(
        cycle_id, CycleState.PROPOSE_IMPROVEMENT, CycleState.TEST_SANDBOX, "sandbox_result", sandbox_result
    )


def evaluate(cycle_id, evaluation):
    return _advance(cycle_id, CycleState.TEST_SANDBOX, CycleState.EVALUATE, "evaluation", evaluation)


def request_approval(cycle_id):
    """Moves the cycle to REQUEST_APPROVAL and raises a Suggestion so it
    shows up wherever pending suggestions are surfaced."""
    from . import proactive

    cycle = _advance(cycle_id, CycleState.EVALUATE, CycleState.REQUEST_APPROVAL, "state", CycleState.REQUEST_APPROVAL)
    proactive.add(
        kind="improvement_deploy",
        message=f"Improvement {cycle_id}: {cycle.proposal}",
        proposed_action="deploy",
        context={"cycle_id": cycle_id},
    )
    return cycle


def deploy(cycle_id, actor):
    guard.assert_operational()
    guard.require_human(actor, f"Deploying improvement {cycle_id}")
    cycle = get(cycle_id)
    if cycle is None:
        raise ValueError(f"No improvement cycle {cycle_id}")
    if cycle.state != CycleState.REQUEST_APPROVAL:
        raise ValueError(f"Cycle {cycle_id} is in {cycle.state}, not ready to deploy.")
    cycle.state = CycleState.DEPLOYED
    cycle.decided_by = actor
    cycle.updated_at = _now()
    cycle.history.append({"ts": cycle.updated_at, "to": cycle.state})
    _save(cycle)
    audit.log_event("improvement_deployed", id=cycle_id, actor=actor, proposal=cycle.proposal)
    return cycle


def reject(cycle_id, actor, reason=""):
    guard.assert_operational()
    guard.require_human(actor, f"Rejecting improvement {cycle_id}")
    cycle = get(cycle_id)
    if cycle is None:
        raise ValueError(f"No improvement cycle {cycle_id}")
    cycle.state = CycleState.REJECTED
    cycle.decided_by = actor
    cycle.updated_at = _now()
    cycle.history.append({"ts": cycle.updated_at, "to": cycle.state, "reason": reason})
    _save(cycle)
    audit.log_event("improvement_rejected", id=cycle_id, actor=actor, reason=reason)
    return cycle

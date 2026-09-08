"""The enforcement layer. Every other module routes its guarded actions
through here instead of re-implementing the checks.

Three properties this module exists to guarantee:

1. Fail closed. If the constitution can't be verified, or the emergency
   stop flag is present, every guarded action refuses to run -- no
   exceptions, no override argument, no "just this once".
2. No self-modification path. PROTECTED_PATHS covers the constitution and
   the audit log. guarded_write() raises before touching either, no
   matter what calls it or with what justification string.
3. No self-approval. require_human() enforces that approval-shaped calls
   (approving a skill, raising the autonomy level, deploying an
   improvement, committing a personality change) are only accepted with
   actor == "user". Code cannot pass actor="assistant" and get through --
   there is no such branch.

This is enforced by ordinary Python, and Python is not a sandbox: anyone
willing to edit this file directly could remove these checks. What this
module *does* guarantee is that the assistant's own reasoning -- the LLM
choosing what to call with what arguments -- has no path around it,
because none of the surrounding modules expose one. Real deployments
should back this with OS-level protections (read-only mounts, a separate
privileged process, etc.); see ARCHITECTURE.md.
"""

import os

from . import constitution, paths


class GuardError(RuntimeError):
    """Base class for everything this module refuses to allow."""


class EmergencyStopActive(GuardError):
    pass


class ConstitutionInvalid(GuardError):
    pass


class ProtectedPathError(GuardError):
    pass


class ApprovalRequiredError(GuardError):
    pass


class AutonomyTooLowError(GuardError):
    pass


def _protected_paths():
    return {
        os.path.realpath(paths.SECURITY_DIR),
        os.path.realpath(paths.AUDIT_LOG_PATH),
    }


def is_stopped():
    return os.path.exists(paths.STOP_FLAG_PATH)


def assert_constitution_valid():
    if not constitution.is_valid():
        raise ConstitutionInvalid(
            "Constitution failed integrity verification. All guarded "
            "actions are blocked until a human resolves this."
        )


def assert_not_stopped():
    if is_stopped():
        raise EmergencyStopActive(
            "Emergency stop is active. Run `jarvis_cli.py resume` (a "
            "direct human action) to clear it before anything else can run."
        )


def assert_operational():
    """The check every guarded action should open with."""
    assert_constitution_valid()
    assert_not_stopped()


def require_human(actor, action_description):
    """Refuse unless a human, not the assistant's own reasoning, is the
    actor approving this action. `actor` is a plain string the caller
    supplies -- there is deliberately no way for the assistant to assert
    "user" on its own behalf from inside a proposal/observe/analyze step;
    only the CLI's interactive commands pass actor="user"."""
    if actor != "user":
        raise ApprovalRequiredError(
            f"{action_description} requires a human actor (got {actor!r}). "
            "The assistant can propose this; only the user can approve it."
        )


def is_protected_path(path):
    real = os.path.realpath(path)
    for protected in _protected_paths():
        if real == protected or real.startswith(protected + os.sep):
            return True
    return False


def guarded_write(path, content, mode="w"):
    """The only write helper jarvis_core modules use for arbitrary files.
    Refuses outright for anything under security/ or the audit log --
    those have their own single-purpose writers (or none at all)."""
    if is_protected_path(path):
        raise ProtectedPathError(f"Refusing to write to protected path: {path}")
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        f.write(content)


def require_autonomy(level_required, current_level, action_description):
    if int(current_level) < int(level_required):
        raise AutonomyTooLowError(
            f"{action_description} requires autonomy level {level_required}, "
            f"current level is {current_level}."
        )

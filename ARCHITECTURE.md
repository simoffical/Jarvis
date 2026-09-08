# Jarvis adaptive development system

This started as a governance layer with no assistant attached to it: the
safety boundaries an adaptive/self-improving assistant would need --
constitution, audit log, approval workflow, autonomy levels, emergency
stop, sandboxing -- as real, tested code, with nothing yet using them.
`voice_agent/` is the first real front-end: a LiveKit real-time voice
agent that sits *underneath* `jarvis_core.guard`, not beside it. Its
tools (`voice_agent/tools.py`) call straight into `jarvis_core`'s own
`guard`/`autonomy`/`skills`/`shutdown` functions -- the same
`guard.require_human()` check that blocks the CLI from self-approving
also blocks the voice agent, because it's the same function. Any further
automation layer (OS control, application launching, hardware) should
follow the same pattern: call into `jarvis_core`, don't reimplement its
checks.

## Layout

```
security/
  constitution.json      immutable rules (R1-R13)
  constitution.sha256     sealed hash of the above
bin/
  emergency_stop.py       zero-dependency kill switch
  reseal_constitution.py  human-only tool to re-seal after an edit
jarvis_core/
  paths.py                every path the package touches, in one place
  constitution.py         loads + hash-verifies the rules; no write path
  guard.py                central fail-closed enforcement
  audit.py                append-only event log
  shutdown.py             emergency stop (trigger/resume)
  autonomy.py             levels 0-5, human-only changes
  skills.py               propose -> approve/reject/revert workflow
  memory.py               pattern/routine observation
  personality.py          versioned profile, propose -> commit -> revert
  goals.py                user-owned long-term goals
  proactive.py            suggestion queue (never auto-executes)
  curiosity.py            bounded question queue
  diagnostics.py          success-rate tracking ("I could improve this")
  improvement.py          OBSERVE..DEPLOY state machine
  sandbox.py              disposable, escape-proof scratch directories
  devpanel.py             status snapshot, built from the modules above
jarvis_cli.py              human-facing front door (the only place that
                            hardcodes actor="user")
tests/test_jarvis_core.py  proves the boundaries below actually hold
voice_agent/
  agent.py                 LiveKit entrypoint: STT -> Claude -> TTS
  tools.py                 function-tools calling straight into jarvis_core
  persona.py               builds the system prompt from personality.current()
  requirements.txt         separate, non-stdlib deps (kept out of jarvis_core)
```

## The boundaries, and how they're actually enforced

**"Never modify its own security boundaries" / "never grant itself
additional permissions."** No function anywhere in `jarvis_core/` opens
`security/constitution.json` or `constitution.sha256` for writing --
verified by `tests/test_jarvis_core.py::test_no_write_path_to_
constitution_anywhere_in_jarvis_core`, which parses every module's AST
and fails if one ever does. The only writer is `bin/reseal_constitution.py`,
a script outside the package that nothing in `jarvis_core` imports or
calls, and which requires a typed `YES` confirmation. Every guarded
action calls `constitution.is_valid()` first; if the file has been
tampered with (hash mismatch), the whole system fails closed.

**"Never conceal important actions" / audit trail.** `audit.py` exposes
`log_event()` and read-only accessors -- there is no `update_event` or
`delete_event` anywhere in its API (also asserted by a test). `guard.
guarded_write()` additionally refuses to write to the audit log path from
any *other* module, so nothing can route around the missing API by
opening the file directly.

**"Cannot independently assign itself goals/permissions" / human-in-the-
-loop.** `guard.require_human(actor, ...)` is called by every state-
changing function that matters: `skills.approve/reject/revert`,
`autonomy.set_level`, `personality.commit/revert_to`, `goals.add`,
`proactive.resolve`, `improvement.deploy/reject`, `shutdown.resume`. All
of them raise `ApprovalRequiredError` unless `actor == "user"`. The
assistant's own code paths (`skills.propose`, `personality.propose`,
`proactive.add`, `improvement.observe/analyze/...`) can only ever reach
a *pending* state. `jarvis_cli.py` is the one file allowed to hardcode
`actor="user"`, because it IS the human typing a command.

`voice_agent/` earns that same right differently: `agent.py` blocks on
`ctx.wait_for_participant(identity=JARVIS_AUTHORIZED_IDENTITY)` before a
session ever starts, so `actor="user"` in `voice_agent/tools.py` is only
ever attached to a session that began with LiveKit itself verifying that
specific identity joined the call -- not because the code trusts anything
the LLM says. `jarvis_core` still does the actual refusing.

**Emergency stop, independent of the assistant.** `data/STOP` is checked
by `guard.assert_operational()` before every guarded action, everywhere,
with no override parameter. `bin/emergency_stop.py` creates that file
using nothing but the standard library -- it does not import
`jarvis_core` at all, so it keeps working even if the assistant's process
is hung or broken. Only `shutdown.resume(actor="user")` clears it.

**Sandbox.** `sandbox.Sandbox` resolves every path against its own root
and raises `SandboxPathEscape` on anything that would leave it (`../..`,
absolute paths). It exposes `write`/`read`/`list`/`dispose` and nothing
else -- no subprocess, no network, no credential access -- so code using
only this API cannot reach the OS or secrets even if it wanted to.
`dispose()` deletes the directory; used as a context manager, disposal is
automatic.

## Honest limits

This is enforced by ordinary Python running with ordinary filesystem
permissions, not a real OS sandbox. Anyone able to edit `jarvis_core/`
directly (not through the assistant's own reasoning, which has no such
tool) could remove these checks. The guarantee this repo actually
delivers is narrower and still useful: **the assistant's own choices --
what it calls, with what arguments -- have no path around the guard**,
because none of the surrounding modules expose one. A production
deployment should add what code alone can't provide:

- OS-level append-only or write-once storage for `data/audit.log`
  (e.g. `chattr +a` on ext4, or a managed log service).
- A read-only mount or separate privileged process for `security/`, so
  even a compromised host process can't write there.
- Process isolation (containers/VMs) for anything wired up to the
  `sandbox` module's future "run code" extension, if one is ever added --
  today it only reads/writes files, deliberately.

## Trying it

```
python3 jarvis_cli.py status
python3 jarvis_cli.py autonomy set 2 --reason "trying safe automation"
python3 jarvis_cli.py skill propose --name "Music Mode" \
    --description "Open FL Studio, Discord, Chrome together" \
    --instructions "Launch the three apps in order" \
    --permission-level 2 --reason "repeated user workflow detected"
python3 jarvis_cli.py skill approve "Music Mode"
python3 jarvis_cli.py audit show
python3 bin/emergency_stop.py "testing"
python3 jarvis_cli.py autonomy set 3   # refused while stopped
python3 jarvis_cli.py resume

python3 -m unittest discover -s tests -v
```

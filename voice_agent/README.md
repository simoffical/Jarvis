# Jarvis voice agent (LiveKit)

Real-time voice front-end for the `jarvis_core` governance layer:

```
your mic --STT (Deepgram)--> Claude (jarvis_core-aware tools) --TTS (ElevenLabs)--> your speakers
```

This is a separate package from `jarvis_core` on purpose -- `jarvis_core`
stays stdlib-only and testable without any of this. Every tool call this
agent can make (`voice_agent/tools.py`) still goes through `jarvis_core`'s
own `guard`/`autonomy`/`skills` checks; nothing here bypasses them.

## Setup

```bash
cd voice_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

1. **LiveKit project** -- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
   Don't have one? Create a free project at https://cloud.livekit.io and
   copy these three values from Settings -> Keys.
2. **Deepgram** -- `DEEPGRAM_API_KEY` from https://console.deepgram.com.
3. **ElevenLabs** -- `ELEVEN_API_KEY` (the plugin reads this exact name,
   not `ELEVENLABS_API_KEY`) from https://elevenlabs.io/app/settings/api-keys.
4. **Anthropic** -- `ANTHROPIC_API_KEY`.
5. **`JARVIS_AUTHORIZED_IDENTITY`** -- see "Identity gate" below. This is
   what stops a stranger who finds your room name from being treated as
   the user who can approve things.

## Run

```bash
python3 agent.py dev     # connects to a LiveKit dev/test room, logs locally
python3 agent.py start   # production worker, registers with your LiveKit project
```

You'll also need a client to actually join the room and talk -- LiveKit's
hosted [Agents Playground](https://agents-playground.livekit.io) works
against any project without writing a client app: sign in with the same
project, join a room, and the worker will pick up the job.

## Identity gate

`agent.py` calls:

```python
participant = await ctx.wait_for_participant(identity=JARVIS_AUTHORIZED_IDENTITY)
```

This blocks until a participant with *exactly* that identity joins, and
that's the identity `voice_agent.tools.JarvisUserdata` carries into every
tool call as `actor="user"`. When you mint an access token for yourself
(the Agents Playground does this for you; a custom client would call
`livekit-server-sdk`'s token API), set the identity field to the same
string as `JARVIS_AUTHORIZED_IDENTITY`. Nobody else joining the room can
trigger an approval-shaped tool call, because the session that carries
`actor="user"` is only ever started for that one identity.

## What the voice agent can and can't do

Read-only and propose-only tools (`get_status`, `list_pending_skills`,
`list_suggestions`, `propose_skill`) run freely -- they can't change
standing behavior. Approval-shaped tools (`approve_skill`, `reject_skill`,
`set_autonomy_level`, `add_goal`, `deploy_improvement`,
`resolve_suggestion`) are only supposed to be called right after you say
so out loud -- `persona.py`'s system prompt says this explicitly. But the
prompt is not the enforcement: `jarvis_core.guard.require_human` is. If
the LLM ever called one of these without you asking, `jarvis_core` itself
would only accept it because the session's `actor` really is `"user"` --
there's no `actor="assistant"` path anywhere in this package. See
`ARCHITECTURE.md` at the repo root for the full boundary.

`engage_emergency_stop` is the one exception: it's always allowed,
no "did you really mean that" gate, because constitution rule R13 requires
the stop to always be available on request. Say "stop" or "emergency
stop" and it fires immediately.

## Known dependency pin

`anthropic<1` is required -- see the comment in `requirements.txt`.
`livekit-plugins-anthropic` 1.8.0 constructs its own `httpx.AsyncClient`
and passes it into the Anthropic SDK; `anthropic>=1.0` rejects that (it
moved to an internal `httpx2` fork). This was hit and confirmed while
building this package; revisit if a newer `livekit-plugins-anthropic`
release fixes it upstream.

## Changing the voice or personality

- **Voice**: set `ELEVENLABS_VOICE_ID` in `.env`, or change
  `DEFAULT_VOICE_ID` in `agent.py`. The current default is Alice - Clear,
  Engaging Educator (`Xb7hH8MSUJpSbSDYk0k2`), a measured/professional
  British female voice.
- **Personality** (formality, sarcasm level, verbosity, etc.): this is
  *not* hardcoded here -- `persona.py` builds the system prompt from
  `jarvis_core.personality.current()`. Change it with
  `jarvis_core.personality.propose()` + `.commit(actor="user")` (or
  `jarvis_cli.py`, once that gets a personality subcommand), the same
  versioned, human-approved path every other behavior change uses.

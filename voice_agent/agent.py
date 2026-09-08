#!/usr/bin/env python3
"""LiveKit Agents entrypoint: gives Jarvis a real-time voice front end.

    STT (Deepgram) -> LLM (Claude, via jarvis_core-aware tools) -> TTS (ElevenLabs)

Run with (from voice_agent/, inside its venv, with .env filled in):

    python3 agent.py dev      # connects to a local/dev room for testing
    python3 agent.py start    # production worker mode

See README.md for the full setup (LiveKit project, API keys, identity gate).
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from livekit.agents import (  # noqa: E402
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import anthropic, deepgram, elevenlabs, silero  # noqa: E402

from jarvis_core import audit  # noqa: E402
from voice_agent import persona, tools  # noqa: E402

logger = logging.getLogger("jarvis-voice-agent")

DEFAULT_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"  # Alice - Clear, Engaging Educator (ElevenLabs)


def prewarm(proc: JobProcess):
    # Voice activity detection is loaded once per worker process, not per
    # call -- this is the standard livekit-agents pattern for keeping
    # call setup fast.
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    authorized_identity = os.environ.get("JARVIS_AUTHORIZED_IDENTITY")
    if not authorized_identity:
        logger.error("JARVIS_AUTHORIZED_IDENTITY is not set -- refusing to start a session "
                      "for an unverified caller. Set it in voice_agent/.env.")
        ctx.shutdown(reason="no authorized identity configured")
        return

    # Blocks until the specific identity we trust joins the room. Anyone
    # else in the room is never treated as the authenticated user, and no
    # approval-shaped tool call in tools.py can be reached without one.
    participant = await ctx.wait_for_participant(identity=authorized_identity)
    audit.log_event("voice_session_started", identity=participant.identity, room=ctx.room.name)

    userdata = tools.JarvisUserdata(identity=participant.identity)

    session = AgentSession[tools.JarvisUserdata](
        userdata=userdata,
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-3"),
        llm=anthropic.LLM(model=os.environ.get("JARVIS_LLM_MODEL", "claude-sonnet-4-6")),
        tts=elevenlabs.TTS(voice_id=os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)),
    )

    agent = Agent(instructions=persona.build_instructions(), tools=tools.TOOLS)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await session.generate_reply(
        instructions="Greet the user briefly, in character, and mention you're ready."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

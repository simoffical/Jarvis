"""Real-time voice front-end for Jarvis, built on LiveKit Agents.

This package is the automation layer ARCHITECTURE.md said would sit
*underneath* jarvis_core.guard, not beside it: every state-changing thing
the voice agent can do still goes through jarvis_core's own approval
checks. It is intentionally a separate, non-stdlib-only package -- see
requirements.txt -- so jarvis_core itself stays dependency-free.
"""

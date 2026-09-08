"""Central location for every path jarvis_core touches.

Keeping paths in one module makes the boundary in guard.py easy to audit:
guard.PROTECTED_PATHS is built directly from the constants here, so nobody
has to hunt through every module to know what is off-limits.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECURITY_DIR = os.path.join(ROOT, "security")
CONSTITUTION_PATH = os.path.join(SECURITY_DIR, "constitution.json")
CONSTITUTION_HASH_PATH = os.path.join(SECURITY_DIR, "constitution.sha256")

DATA_DIR = os.path.join(ROOT, "data")
AUDIT_LOG_PATH = os.path.join(DATA_DIR, "audit.log")
STOP_FLAG_PATH = os.path.join(DATA_DIR, "STOP")
AUTONOMY_PATH = os.path.join(DATA_DIR, "autonomy.json")
PERSONALITY_PATH = os.path.join(DATA_DIR, "personality.json")
GOALS_PATH = os.path.join(DATA_DIR, "goals.json")
SUGGESTIONS_PATH = os.path.join(DATA_DIR, "suggestions.json")
CURIOSITY_PATH = os.path.join(DATA_DIR, "curiosity.json")
DIAGNOSTICS_LOG_PATH = os.path.join(DATA_DIR, "diagnostics.jsonl")

SKILLS_DIR = os.path.join(DATA_DIR, "skills")
MEMORY_DIR = os.path.join(DATA_DIR, "memory")
MEMORY_EVENTS_PATH = os.path.join(MEMORY_DIR, "events.jsonl")
SANDBOX_DIR = os.path.join(DATA_DIR, "sandbox")
IMPROVEMENTS_DIR = os.path.join(DATA_DIR, "improvements")


def ensure_data_dirs():
    """Create the mutable data/ tree. Never touches security/."""
    for d in (DATA_DIR, SKILLS_DIR, MEMORY_DIR, SANDBOX_DIR, IMPROVEMENTS_DIR):
        os.makedirs(d, exist_ok=True)

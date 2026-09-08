#!/usr/bin/env python3
"""Recompute security/constitution.sha256 after a deliberate hand-edit of
security/constitution.json.

This script is the ONLY place in this repository that writes to the
constitution's hash file. It is not imported by jarvis_core, not callable
from jarvis_cli.py, and not reachable through anything the assistant runs
on its own. Changing the constitution is a human action taken directly on
the filesystem, outside the assistant's authority -- this script exists
purely to keep the integrity hash in sync after that human action, and it
asks for explicit confirmation before doing so.

Usage:
    python3 bin/reseal_constitution.py
"""

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSTITUTION_PATH = os.path.join(ROOT, "security", "constitution.json")
HASH_PATH = os.path.join(ROOT, "security", "constitution.sha256")


def main():
    if not os.path.isfile(CONSTITUTION_PATH):
        print(f"No constitution found at {CONSTITUTION_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CONSTITUTION_PATH, "rb") as f:
        data = f.read()
    new_hash = hashlib.sha256(data).hexdigest()

    old_hash = None
    if os.path.isfile(HASH_PATH):
        with open(HASH_PATH, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

    print(f"Constitution file: {CONSTITUTION_PATH}")
    print(f"Current sealed hash: {old_hash}")
    print(f"Newly computed hash: {new_hash}")

    if old_hash == new_hash:
        print("Already sealed. Nothing to do.")
        return

    answer = input(
        "Type YES to reseal the constitution with the new hash "
        "(only do this after you personally reviewed the rule changes): "
    )
    if answer.strip() != "YES":
        print("Aborted. Constitution left unsealed (integrity check will fail).")
        sys.exit(1)

    with open(HASH_PATH, "w", encoding="utf-8") as f:
        f.write(new_hash + "\n")
    print("Resealed.")


if __name__ == "__main__":
    main()

"""Loads and verifies the hard constitution.

Nothing in this module -- or anywhere else in jarvis_core -- writes to
security/constitution.json or security/constitution.sha256. Search the
package if you doubt it; there is no open(..., "w") targeting SECURITY_DIR
anywhere under jarvis_core/. The only writer is bin/reseal_constitution.py,
a standalone human-run script outside this package.

If the file is missing or its hash doesn't match what was sealed, this
module refuses to hand back any rules. guard.py treats that as fatal and
fails every guarded action closed, system-wide, until a human fixes it.
"""

import hashlib
import json

from . import paths


class ConstitutionIntegrityError(RuntimeError):
    """The constitution is missing, unreadable, or has been tampered with."""


_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache

    try:
        with open(paths.CONSTITUTION_PATH, "rb") as f:
            raw = f.read()
    except OSError as exc:
        raise ConstitutionIntegrityError(
            f"Cannot read constitution at {paths.CONSTITUTION_PATH}: {exc}"
        ) from exc

    try:
        with open(paths.CONSTITUTION_HASH_PATH, "r", encoding="utf-8") as f:
            sealed_hash = f.read().strip()
    except OSError as exc:
        raise ConstitutionIntegrityError(
            f"Cannot read sealed hash at {paths.CONSTITUTION_HASH_PATH}: {exc}"
        ) from exc

    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != sealed_hash:
        raise ConstitutionIntegrityError(
            "Constitution has been modified since it was last sealed "
            f"(expected {sealed_hash}, got {actual_hash}). Refusing to "
            "load. Run bin/reseal_constitution.py as a human, after "
            "reviewing the change, before this system will operate again."
        )

    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConstitutionIntegrityError(f"Constitution is not valid JSON: {exc}") from exc

    rules = doc.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ConstitutionIntegrityError("Constitution has no rules.")

    _cache = doc
    return _cache


def rules():
    """Return the list of {id, text} rule dicts. Raises on tampering."""
    return list(_load()["rules"])


def is_valid():
    try:
        _load()
        return True
    except ConstitutionIntegrityError:
        return False


def describe_violation_check():
    """Human-readable summary, used by the CLI's `status` command."""
    try:
        doc = _load()
        return f"OK - {doc['name']} v{doc['version']}, {len(doc['rules'])} rules sealed"
    except ConstitutionIntegrityError as exc:
        return f"INVALID - {exc}"

"""Disposable, reversible experiment sandbox (spec section 4).

A Sandbox is a fresh directory under data/sandbox/<id>/. Its write()/
read()/list() helpers resolve the requested path and refuse anything that
escapes the sandbox root (blocks "../../something" and absolute-path
tricks alike). There is no subprocess, network, or credential access
exposed anywhere in this module -- not filtered out, just never provided
-- so code using only this API cannot reach the OS, other machines, or
secrets even if it wanted to. dispose() deletes the directory; using the
object as a context manager disposes automatically on exit, so a crashed
experiment doesn't leave debris behind.
"""

import os
import shutil
import uuid

from . import audit, paths


class SandboxPathEscape(RuntimeError):
    pass


class Sandbox:
    def __init__(self, label=""):
        os.makedirs(paths.SANDBOX_DIR, exist_ok=True)
        self.id = f"{uuid.uuid4().hex[:8]}-{label}" if label else uuid.uuid4().hex[:8]
        self.path = os.path.join(paths.SANDBOX_DIR, self.id)
        os.makedirs(self.path, exist_ok=False)
        self._disposed = False
        audit.log_event("sandbox_created", id=self.id, label=label)

    def _resolve(self, relpath):
        root = os.path.realpath(self.path)
        target = os.path.realpath(os.path.join(self.path, relpath))
        if target != root and not target.startswith(root + os.sep):
            raise SandboxPathEscape(f"{relpath!r} escapes the sandbox root.")
        return target

    def write(self, relpath, content):
        target = self._resolve(relpath)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def read(self, relpath):
        with open(self._resolve(relpath), "r", encoding="utf-8") as f:
            return f.read()

    def list(self):
        listing = []
        for dirpath, _dirnames, filenames in os.walk(self.path):
            for name in filenames:
                full = os.path.join(dirpath, name)
                listing.append(os.path.relpath(full, self.path))
        return sorted(listing)

    def dispose(self):
        if self._disposed:
            return
        shutil.rmtree(self.path, ignore_errors=True)
        self._disposed = True
        audit.log_event("sandbox_disposed", id=self.id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.dispose()
        return False


def active_sandboxes():
    if not os.path.isdir(paths.SANDBOX_DIR):
        return []
    return sorted(
        d for d in os.listdir(paths.SANDBOX_DIR) if os.path.isdir(os.path.join(paths.SANDBOX_DIR, d))
    )

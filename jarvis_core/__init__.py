"""Jarvis adaptive development system.

A small, real implementation of "growing intelligence with fixed
constitutional boundaries": the assistant can learn preferences, propose
skills, run sandboxed experiments, and adapt its personality -- but every
one of those capabilities is gated by a guard module it cannot rewrite,
an immutable constitution it cannot edit, and an audit log it cannot erase.

This package intentionally does NOT include OS automation, application
launching, or hardware control. It governs behavior; it does not grant it.
Wiring a real automation layer underneath jarvis_core.guard is a separate,
later decision -- and that layer would still have to pass through the
same guard checks defined here.
"""

VERSION = "0.1.0"
SYSTEM_NAME = "Jarvis"

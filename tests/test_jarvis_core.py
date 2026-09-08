#!/usr/bin/env python3
"""Tests for the safety boundaries jarvis_core is supposed to guarantee.

Run with: python3 -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_core import (  # noqa: E402
    audit,
    autonomy,
    constitution,
    curiosity,
    diagnostics,
    devpanel,
    goals,
    guard,
    improvement,
    memory,
    paths,
    personality,
    proactive,
    sandbox,
    shutdown,
    skills,
)

PATCHED_ATTRS = [
    "DATA_DIR",
    "AUDIT_LOG_PATH",
    "STOP_FLAG_PATH",
    "AUTONOMY_PATH",
    "PERSONALITY_PATH",
    "GOALS_PATH",
    "SUGGESTIONS_PATH",
    "CURIOSITY_PATH",
    "DIAGNOSTICS_LOG_PATH",
    "SKILLS_DIR",
    "MEMORY_DIR",
    "MEMORY_EVENTS_PATH",
    "SANDBOX_DIR",
    "IMPROVEMENTS_DIR",
]


class JarvisTestCase(unittest.TestCase):
    """Redirects every mutable-data path into a throwaway temp dir so tests
    never touch the real security/ or data/ directories. Deliberately does
    NOT touch CONSTITUTION_PATH / CONSTITUTION_HASH_PATH -- those stay
    pointed at the real, sealed repo files unless a specific test says
    otherwise."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jarvis-test-")
        self._originals = {name: getattr(paths, name) for name in PATCHED_ATTRS}

        data_dir = os.path.join(self._tmp, "data")
        setattr(paths, "DATA_DIR", data_dir)
        setattr(paths, "AUDIT_LOG_PATH", os.path.join(data_dir, "audit.log"))
        setattr(paths, "STOP_FLAG_PATH", os.path.join(data_dir, "STOP"))
        setattr(paths, "AUTONOMY_PATH", os.path.join(data_dir, "autonomy.json"))
        setattr(paths, "PERSONALITY_PATH", os.path.join(data_dir, "personality.json"))
        setattr(paths, "GOALS_PATH", os.path.join(data_dir, "goals.json"))
        setattr(paths, "SUGGESTIONS_PATH", os.path.join(data_dir, "suggestions.json"))
        setattr(paths, "CURIOSITY_PATH", os.path.join(data_dir, "curiosity.json"))
        setattr(paths, "DIAGNOSTICS_LOG_PATH", os.path.join(data_dir, "diagnostics.jsonl"))
        setattr(paths, "SKILLS_DIR", os.path.join(data_dir, "skills"))
        setattr(paths, "MEMORY_DIR", os.path.join(data_dir, "memory"))
        setattr(paths, "MEMORY_EVENTS_PATH", os.path.join(data_dir, "memory", "events.jsonl"))
        setattr(paths, "SANDBOX_DIR", os.path.join(data_dir, "sandbox"))
        setattr(paths, "IMPROVEMENTS_DIR", os.path.join(data_dir, "improvements"))
        paths.ensure_data_dirs()

        constitution._cache = None

    def tearDown(self):
        for name, value in self._originals.items():
            setattr(paths, name, value)
        shutil.rmtree(self._tmp, ignore_errors=True)
        constitution._cache = None


class ConstitutionTests(JarvisTestCase):
    def test_real_constitution_is_valid_and_has_thirteen_rules(self):
        self.assertTrue(constitution.is_valid())
        self.assertEqual(len(constitution.rules()), 13)

    def test_tampering_is_detected(self):
        tampered_dir = tempfile.mkdtemp(prefix="jarvis-tamper-")
        try:
            tampered_path = os.path.join(tampered_dir, "constitution.json")
            with open(tampered_path, "w", encoding="utf-8") as f:
                f.write('{"name": "x", "version": "1.0", "rules": [{"id": "R1", "text": "anything goes"}]}')

            original_path = paths.CONSTITUTION_PATH
            paths.CONSTITUTION_PATH = tampered_path
            constitution._cache = None
            try:
                self.assertFalse(constitution.is_valid())
                with self.assertRaises(constitution.ConstitutionIntegrityError):
                    constitution.rules()
            finally:
                paths.CONSTITUTION_PATH = original_path
                constitution._cache = None
        finally:
            shutil.rmtree(tampered_dir, ignore_errors=True)

    def test_no_write_path_to_constitution_anywhere_in_jarvis_core(self):
        """No open()/write call in jarvis_core targets anything derived
        from CONSTITUTION_PATH, CONSTITUTION_HASH_PATH, or SECURITY_DIR.
        guard.py itself is allowed to *mention* SECURITY_DIR (it has to,
        to compare against it) but never as a write target."""
        import ast
        import jarvis_core

        write_modes = {"w", "a", "x", "w+", "a+", "wb", "ab", "xb"}
        pkg_dir = os.path.dirname(jarvis_core.__file__)

        for fname in os.listdir(pkg_dir):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(pkg_dir, fname), "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=fname)

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open"):
                    continue

                mode = None
                if len(node.args) >= 2:
                    mode = getattr(node.args[1], "value", None)
                for kw in node.keywords:
                    if kw.arg == "mode":
                        mode = getattr(kw.value, "value", None)
                if mode not in write_modes:
                    continue

                target_src = ast.unparse(node.args[0]) if node.args else ""
                self.assertNotIn(
                    "CONSTITUTION", target_src,
                    f"{fname} writes to a constitution-derived path: {target_src}",
                )
                self.assertNotIn(
                    "SECURITY_DIR", target_src,
                    f"{fname} writes to a security-dir-derived path: {target_src}",
                )


class GuardTests(JarvisTestCase):
    def test_guarded_write_refuses_security_dir(self):
        target = os.path.join(paths.SECURITY_DIR, "sneaky.json")
        with self.assertRaises(guard.ProtectedPathError):
            guard.guarded_write(target, "{}")

    def test_guarded_write_refuses_audit_log(self):
        with self.assertRaises(guard.ProtectedPathError):
            guard.guarded_write(paths.AUDIT_LOG_PATH, "tampered\n")

    def test_guarded_write_allows_ordinary_data_path(self):
        target = os.path.join(paths.DATA_DIR, "ok.json")
        guard.guarded_write(target, "{}")
        self.assertTrue(os.path.isfile(target))

    def test_require_human_rejects_non_user_actor(self):
        with self.assertRaises(guard.ApprovalRequiredError):
            guard.require_human("assistant", "doing a thing")
        guard.require_human("user", "doing a thing")  # should not raise


class EmergencyStopTests(JarvisTestCase):
    def test_stop_blocks_guarded_actions_and_resume_requires_human(self):
        autonomy.set_level(2, actor="user")  # works before stop

        shutdown.trigger("testing", source="user")
        self.assertTrue(shutdown.is_stopped())

        with self.assertRaises(guard.EmergencyStopActive):
            autonomy.set_level(3, actor="user")
        with self.assertRaises(guard.EmergencyStopActive):
            skills.propose("x", "y", [], "z", "in", "out", 1)

        with self.assertRaises(guard.ApprovalRequiredError):
            shutdown.resume(actor="assistant")
        self.assertTrue(shutdown.is_stopped(), "non-human resume must not clear the stop")

        shutdown.resume(actor="user")
        self.assertFalse(shutdown.is_stopped())
        autonomy.set_level(3, actor="user")  # works again


class AutonomyTests(JarvisTestCase):
    def test_only_human_actor_can_change_level(self):
        with self.assertRaises(guard.ApprovalRequiredError):
            autonomy.set_level(4, actor="assistant")
        self.assertEqual(autonomy.get_level(), autonomy.AutonomyLevel.CONVERSATION_ONLY)

        autonomy.set_level(4, actor="user", reason="approved workflow test")
        self.assertEqual(autonomy.get_level(), autonomy.AutonomyLevel.PROACTIVE_APPROVED_WORKFLOWS)
        self.assertEqual(len(autonomy.get_history()), 1)


class SkillTests(JarvisTestCase):
    def test_propose_then_approve_workflow(self):
        skills.propose(
            name="Music Mode",
            description="Open FL Studio, Discord, Chrome",
            required_tools=["app_launcher"],
            instructions="Launch the three apps in order.",
            input_format="none",
            output_format="none",
            permission_level=2,
            reason="repeated user workflow detected",
        )
        skill = skills.get("Music Mode")
        self.assertEqual(skill.status, skills.SkillStatus.PENDING_APPROVAL)

        with self.assertRaises(guard.ApprovalRequiredError):
            skills.approve("Music Mode", actor="assistant")

        activated = skills.approve("Music Mode", actor="user")
        self.assertEqual(activated.status, skills.SkillStatus.ACTIVE)

        with self.assertRaises(ValueError):
            skills.approve("Music Mode", actor="user")  # already active

    def test_revert_restores_previous_version(self):
        skills.propose("Test Skill", "d", [], "i", "in", "out", 1)
        skills.approve("Test Skill", actor="user")
        before = skills.get("Test Skill")

        skill = skills.get("Test Skill")
        skill.version = "2.0"
        skills._save(skill)

        reverted = skills.revert("Test Skill", actor="user")
        self.assertEqual(reverted.version, before.version)

    def test_reject_sets_status(self):
        skills.propose("Bad Idea", "d", [], "i", "in", "out", 1)
        rejected = skills.reject("Bad Idea", actor="user", reason="not useful")
        self.assertEqual(rejected.status, skills.SkillStatus.REJECTED)


class AuditTests(JarvisTestCase):
    def test_events_are_recorded_in_order(self):
        audit.log_event("test_event_one", value=1)
        audit.log_event("test_event_two", value=2)
        events = audit.read_events()
        self.assertEqual([e["event"] for e in events], ["test_event_one", "test_event_two"])

    def test_no_mutation_api_exists(self):
        self.assertFalse(hasattr(audit, "delete_event"))
        self.assertFalse(hasattr(audit, "update_event"))
        self.assertFalse(hasattr(audit, "clear"))


class SandboxTests(JarvisTestCase):
    def test_path_escape_is_blocked(self):
        with sandbox.Sandbox("test") as sb:
            with self.assertRaises(sandbox.SandboxPathEscape):
                sb.write("../escape.txt", "nope")
            with self.assertRaises(sandbox.SandboxPathEscape):
                sb.write("/etc/passwd", "nope")

    def test_write_read_and_disposal(self):
        sb = sandbox.Sandbox("test2")
        sb.write("notes/idea.txt", "hello")
        self.assertEqual(sb.read("notes/idea.txt"), "hello")
        self.assertIn("notes/idea.txt", sb.list())
        path = sb.path
        sb.dispose()
        self.assertFalse(os.path.exists(path))


class ImprovementLoopTests(JarvisTestCase):
    def test_full_cycle_requires_order_and_human_deploy(self):
        cycle = improvement.observe("File organization seems inefficient.")
        cycle = improvement.analyze(cycle.id, "Users re-sort the same folder weekly.")
        cycle = improvement.identify_problem(cycle.id, "No stable sort order.")
        cycle = improvement.propose_improvement(cycle.id, "Sort by project tag then date.")

        with self.assertRaises(ValueError):
            improvement.deploy(cycle.id, actor="user")  # not in REQUEST_APPROVAL yet

        cycle = improvement.record_sandbox_test(cycle.id, "Tested on 50 sample files, no errors.")
        cycle = improvement.evaluate(cycle.id, "Consistently faster to navigate.")
        cycle = improvement.request_approval(cycle.id)
        self.assertEqual(cycle.state, improvement.CycleState.REQUEST_APPROVAL)

        with self.assertRaises(guard.ApprovalRequiredError):
            improvement.deploy(cycle.id, actor="assistant")

        deployed = improvement.deploy(cycle.id, actor="user")
        self.assertEqual(deployed.state, improvement.CycleState.DEPLOYED)
        self.assertEqual(deployed.decided_by, "user")


class PersonalityTests(JarvisTestCase):
    def test_default_profile_matches_seed(self):
        current = personality.current()
        self.assertEqual(current.version, "1.0")
        self.assertEqual(current.sarcasm_level, 4)

    def test_propose_then_commit_requires_human(self):
        new_profile = personality.PersonalityProfile(
            version="1.1",
            formality="lower",
            verbosity="more detailed",
            humor_style="same",
            sarcasm_level=2,
            terms_of_address="sir",
        )
        personality.propose(new_profile, reason="user asked for less sarcasm")

        with self.assertRaises(guard.ApprovalRequiredError):
            personality.commit(actor="assistant")

        applied = personality.commit(actor="user")
        self.assertEqual(applied.version, "1.1")

        reverted = personality.revert_to("1.0", actor="user")
        self.assertEqual(reverted.version, "1.0")


class MemoryTests(JarvisTestCase):
    def test_routine_detection_needs_repetition(self):
        for session in ("s1", "s2"):
            memory.record_event("app_open", session=session, app="FL Studio")
            memory.record_event("app_open", session=session, app="Discord")
            memory.record_event("app_open", session=session, app="Chrome")
        self.assertEqual(memory.suggest_routines(min_repeats=3), [])

        memory.record_event("app_open", session="s3", app="FL Studio")
        memory.record_event("app_open", session="s3", app="Discord")
        memory.record_event("app_open", session="s3", app="Chrome")

        candidates = memory.suggest_routines(min_repeats=3)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["apps"], ["FL Studio", "Discord", "Chrome"])
        self.assertEqual(candidates[0]["occurrences"], 3)


class CuriosityTests(JarvisTestCase):
    def test_bounded_open_questions(self):
        ids = [curiosity.raise_question(f"why {i}?").id for i in range(curiosity.MAX_OPEN)]
        with self.assertRaises(RuntimeError):
            curiosity.raise_question("one too many?")

        with self.assertRaises(ValueError):
            curiosity.terminate(ids[0], reason="")

        curiosity.terminate(ids[0], reason="task_complete")
        curiosity.raise_question("now there's room")  # should not raise


class GoalsAndSuggestionsTests(JarvisTestCase):
    def test_goal_requires_human_and_can_spawn_suggestion(self):
        with self.assertRaises(guard.ApprovalRequiredError):
            goals.add("Help me learn Blender.", actor="assistant")

        goal = goals.add("Help me learn Blender.", actor="user")
        suggestion = goals.propose_action(goal.id, "You could start with the donut tutorial.")
        self.assertEqual(proactive.list_pending()[0]["id"], suggestion.id)

        with self.assertRaises(guard.ApprovalRequiredError):
            proactive.resolve(suggestion.id, accepted=True, actor="assistant")

        resolved = proactive.resolve(suggestion.id, accepted=True, actor="user")
        self.assertEqual(resolved["status"], proactive.SuggestionStatus.ACCEPTED)


class DiagnosticsTests(JarvisTestCase):
    def test_success_rate_and_flagging(self):
        for success in [True, True, False, False, False]:
            diagnostics.record_result("sort_files", success)
        self.assertAlmostEqual(diagnostics.success_rate("sort_files"), 0.4)
        self.assertTrue(diagnostics.should_flag("sort_files", threshold=0.7))
        self.assertFalse(diagnostics.should_flag("unknown_task"))


class DevPanelTests(JarvisTestCase):
    def test_render_smoke(self):
        text = devpanel.render()
        self.assertIn("SYSTEM VERSION", text)
        self.assertIn("AUTONOMY", text)
        self.assertIn("CONSTITUTION", text)


if __name__ == "__main__":
    unittest.main()

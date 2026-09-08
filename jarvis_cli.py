#!/usr/bin/env python3
"""Command-line front door to jarvis_core.

Every command here that changes standing state runs with actor="user" --
this file IS the human interface. It's the only place in the repository
allowed to hardcode that string; jarvis_core modules themselves never
assume who is calling them.

Usage:
    python3 jarvis_cli.py status
    python3 jarvis_cli.py autonomy show
    python3 jarvis_cli.py autonomy set 2 --reason "trying safe automation"
    python3 jarvis_cli.py skill propose --name "Music Mode" ...
    python3 jarvis_cli.py skill approve "Music Mode"
    python3 jarvis_cli.py audit show -n 20
    python3 jarvis_cli.py stop "taking a break"
    python3 jarvis_cli.py resume
"""

import argparse
import sys

from jarvis_core import (
    audit,
    autonomy,
    devpanel,
    goals,
    guard,
    paths,
    proactive,
    shutdown,
    skills,
)

ACTOR = "user"  # this CLI is a human typing commands; see module docstring


def cmd_status(_args):
    print(devpanel.render())


def cmd_autonomy_show(_args):
    level = autonomy.get_level()
    print(f"Level {int(level)}: {autonomy.DESCRIPTIONS[level]}")


def cmd_autonomy_set(args):
    level = autonomy.set_level(args.level, actor=ACTOR, reason=args.reason or "")
    print(f"Autonomy set to level {int(level)}: {autonomy.DESCRIPTIONS[level]}")


def cmd_skill_propose(args):
    skill = skills.propose(
        name=args.name,
        description=args.description,
        required_tools=args.tools or [],
        instructions=args.instructions,
        input_format=args.input_format,
        output_format=args.output_format,
        permission_level=args.permission_level,
        reason=args.reason or "",
    )
    print(f"Proposed skill {skill.name!r} (status: {skill.status}). Awaiting approval.")


def cmd_skill_approve(args):
    skill = skills.approve(args.name, actor=ACTOR)
    print(f"Skill {skill.name!r} is now {skill.status}.")


def cmd_skill_reject(args):
    skill = skills.reject(args.name, actor=ACTOR, reason=args.reason or "")
    print(f"Skill {skill.name!r} is now {skill.status}.")


def cmd_skill_revert(args):
    skill = skills.revert(args.name, actor=ACTOR)
    print(f"Skill {skill.name!r} reverted to version {skill.version}.")


def cmd_skill_list(args):
    for skill in skills.list_skills(status=args.status):
        print(f"  [{skill.status:16}] {skill.name} (v{skill.version})")


def cmd_goal_add(args):
    goal = goals.add(args.text, actor=ACTOR)
    print(f"Goal added: {goal.id} - {goal.text}")


def cmd_goal_list(_args):
    for g in goals.list_goals():
        print(f"  [{g['status']:8}] {g['id']}  {g['text']}")


def cmd_suggestion_list(_args):
    for s in proactive.list_pending():
        print(f"  {s['id']}  ({s['kind']}) {s['message']}")


def cmd_suggestion_accept(args):
    s = proactive.resolve(args.id, accepted=True, actor=ACTOR)
    print(f"Suggestion {s['id']} accepted. (Nothing executes automatically -- "
          f"use the matching approve/deploy command for the underlying change.)")


def cmd_suggestion_dismiss(args):
    s = proactive.resolve(args.id, accepted=False, actor=ACTOR)
    print(f"Suggestion {s['id']} dismissed.")


def cmd_audit_show(args):
    for e in audit.read_events(event=args.type, limit=args.n):
        print(f"{e['ts']}  {e['event']}  {({k: v for k, v in e.items() if k not in ('ts', 'event')})}")


def cmd_stop(args):
    shutdown.trigger(reason=args.reason or "manual stop", source=ACTOR)
    print("Emergency stop engaged. All guarded actions will refuse to run.")


def cmd_resume(_args):
    shutdown.resume(actor=ACTOR)
    print("Emergency stop cleared.")


def build_parser():
    parser = argparse.ArgumentParser(description="Jarvis adaptive development system CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show the development panel").set_defaults(func=cmd_status)

    p_auto = sub.add_parser("autonomy", help="Manage autonomy level")
    auto_sub = p_auto.add_subparsers(dest="autonomy_command", required=True)
    auto_sub.add_parser("show").set_defaults(func=cmd_autonomy_show)
    p_auto_set = auto_sub.add_parser("set")
    p_auto_set.add_argument("level", type=int, choices=range(0, 6))
    p_auto_set.add_argument("--reason", default="")
    p_auto_set.set_defaults(func=cmd_autonomy_set)

    p_skill = sub.add_parser("skill", help="Manage skills")
    skill_sub = p_skill.add_subparsers(dest="skill_command", required=True)

    p_propose = skill_sub.add_parser("propose")
    p_propose.add_argument("--name", required=True)
    p_propose.add_argument("--description", required=True)
    p_propose.add_argument("--tools", nargs="*", default=[])
    p_propose.add_argument("--instructions", required=True)
    p_propose.add_argument("--input-format", dest="input_format", default="")
    p_propose.add_argument("--output-format", dest="output_format", default="")
    p_propose.add_argument("--permission-level", dest="permission_level", type=int, default=1)
    p_propose.add_argument("--reason", default="")
    p_propose.set_defaults(func=cmd_skill_propose)

    p_approve = skill_sub.add_parser("approve")
    p_approve.add_argument("name")
    p_approve.set_defaults(func=cmd_skill_approve)

    p_reject = skill_sub.add_parser("reject")
    p_reject.add_argument("name")
    p_reject.add_argument("--reason", default="")
    p_reject.set_defaults(func=cmd_skill_reject)

    p_revert = skill_sub.add_parser("revert")
    p_revert.add_argument("name")
    p_revert.set_defaults(func=cmd_skill_revert)

    p_list = skill_sub.add_parser("list")
    p_list.add_argument("--status", default=None)
    p_list.set_defaults(func=cmd_skill_list)

    p_goal = sub.add_parser("goal", help="Manage long-term goals")
    goal_sub = p_goal.add_subparsers(dest="goal_command", required=True)
    p_goal_add = goal_sub.add_parser("add")
    p_goal_add.add_argument("text")
    p_goal_add.set_defaults(func=cmd_goal_add)
    goal_sub.add_parser("list").set_defaults(func=cmd_goal_list)

    p_suggestion = sub.add_parser("suggestion", help="Review proactive suggestions")
    suggestion_sub = p_suggestion.add_subparsers(dest="suggestion_command", required=True)
    suggestion_sub.add_parser("list").set_defaults(func=cmd_suggestion_list)
    p_accept = suggestion_sub.add_parser("accept")
    p_accept.add_argument("id")
    p_accept.set_defaults(func=cmd_suggestion_accept)
    p_dismiss = suggestion_sub.add_parser("dismiss")
    p_dismiss.add_argument("id")
    p_dismiss.set_defaults(func=cmd_suggestion_dismiss)

    p_audit = sub.add_parser("audit", help="Inspect the audit log")
    audit_sub = p_audit.add_subparsers(dest="audit_command", required=True)
    p_audit_show = audit_sub.add_parser("show")
    p_audit_show.add_argument("-n", type=int, default=20)
    p_audit_show.add_argument("--type", default=None)
    p_audit_show.set_defaults(func=cmd_audit_show)

    p_stop = sub.add_parser("stop", help="Engage the emergency stop")
    p_stop.add_argument("reason", nargs="?", default="")
    p_stop.set_defaults(func=cmd_stop)

    sub.add_parser("resume", help="Clear the emergency stop").set_defaults(func=cmd_resume)

    return parser


def main(argv=None):
    paths.ensure_data_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (guard.GuardError, ValueError, RuntimeError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

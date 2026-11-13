"""`setup`: the entry point. With no command it opens the setup window.

  setup                     the setup wizard in the console window (see cli/ui_launch.py)
  setup ui [tool]           the same, opened at one tool's steps
  setup --no-ui [tool]      the interactive terminal setup (resumes where it stopped)
  setup <tool>              set up (or redo) one tool in the terminal
  setup tour [topic]        the guided tour of GUIDE.md (--json: its sections, for the wizard)
  setup status              each tool's platform, status and placeholders left
                            (--json: each tool's health for the console's Tools page)
  setup config [tool]       change a tool's settings (--list, --set id=value for the agent)
  setup intro               the intro paragraph (the wizard's first screen)
The rest (list, prereqs, choose, apply, mark, plan, wire, verify, samples) are the
non-interactive commands the setup skill and the wizard call; see cli/agent.py.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from signal_setup import health, platforms, progress, registry, settings
from signal_setup.cli import agent, config, ui_launch
from signal_setup.intro import intro_text
from signal_setup.ui import run_setup
from signal_setup.ui.tour import run as run_tour
from signal_setup.ui.tour import sections as tour_sections

NO_UI_FLAG = "--no-ui"

# tools/setup/src/signal_setup/cli/main.py -> the repo root is five folders up.
REPO_ROOT = Path(__file__).resolve().parents[5]


def _ids(text: str) -> list[str]:
    """Comma-separated tool ids as a list."""
    return [part.strip() for part in text.split(",") if part.strip()]


def _parser() -> argparse.ArgumentParser:
    """The parser for every command except the bare `setup` and `setup <tool>`."""
    parser = argparse.ArgumentParser(prog="setup", description="Set up Signal's tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("ui").add_argument("tool", nargs="?")
    sub.add_parser("intro")
    conf = sub.add_parser("config")
    conf.add_argument("tool", nargs="?")
    conf.add_argument("--list", action="store_true")
    conf.add_argument("--set", action="append", default=[], metavar="ID=VALUE")
    tour = sub.add_parser("tour")
    tour.add_argument("topic", nargs="?", default="")
    tour.add_argument("--json", action="store_true")
    sub.add_parser("list")
    sub.add_parser("prereqs").add_argument("--tools", type=_ids, default=[])
    sub.add_parser("choose").add_argument("tools", type=_ids)
    apply = sub.add_parser("apply")
    apply.add_argument("tool")
    apply.add_argument("step")
    apply.add_argument("--answer", choices=("yes", "no"))
    apply.add_argument("--value")
    mark = sub.add_parser("mark")
    mark.add_argument("tool")
    mark.add_argument("step")
    mark.add_argument("status", choices=(progress.DONE, progress.SKIPPED))
    sub.add_parser("plan")
    sub.add_parser("wire").add_argument("--yes", action="store_true")
    sub.add_parser("verify").add_argument("tools", nargs="?", type=_ids, default=[])
    samples = sub.add_parser("samples")
    samples.add_argument("action", choices=("files", "paste", "mail", "keep", "count"))
    samples.add_argument("args", nargs="*")
    samples.add_argument("--kind", default="writing")
    return parser


def _status(root: Path, as_json: bool) -> int:
    """Print one line per tool: status, platform label, and any placeholders left.

    With `as_json`, each tool's health (active, down, not set up) as JSON instead.
    """
    if as_json:
        print(json.dumps(health.health_rows(root), indent=2))
        return 0
    data, platform = progress.load(root), platforms.current()
    for tool in registry.load():
        status = progress.tool_status(data, tool, platform) or "not set up"
        left = settings.tool_leftovers(root, tool, data)
        note = f"  placeholders left: {', '.join(left)}" if left else ""
        print(f"{tool.id:12} {status:10} {platforms.label(tool)}{note}")
    return 0


def _config(root: Path, args: argparse.Namespace) -> int:
    """`setup config`: --list and --set need a tool; with neither it's interactive."""
    if (args.list or args.set) and not args.tool:
        raise KeyError("--list and --set need a tool id")
    if args.list:
        return config.list_settings(root, args.tool)
    if args.set:
        return config.set_settings(root, args.tool, args.set)
    return config.interactive(root, args.tool)


def _tour(root: Path, topic: str, as_json: bool) -> int:
    """The tour at the terminal, or with `as_json` every section as {heading, body}."""
    if as_json:
        rows = [{"heading": h, "body": b} for h, b in tour_sections(root)]
        print(json.dumps(rows, indent=2))
        return 0
    run_tour(root, topic)
    return 0


def _dispatch(root: Path, args: argparse.Namespace) -> int:
    """Run the parsed command."""
    commands = {
        "status": lambda: _status(root, args.json),
        "ui": lambda: ui_launch.launch(root, args.tool),
        "intro": lambda: print(intro_text()) or 0,
        "config": lambda: _config(root, args),
        "tour": lambda: _tour(root, args.topic, args.json),
        "list": lambda: agent.list_tools(root),
        "prereqs": lambda: agent.check_prereqs(args.tools),
        "choose": lambda: agent.choose(root, args.tools),
        "apply": lambda: agent.apply(root, args.tool, args.step, args.answer, args.value),
        "mark": lambda: agent.mark(root, args.tool, args.step, args.status),
        "plan": lambda: agent.plan(root),
        "wire": lambda: agent.wire(root, args.yes),
        "verify": lambda: agent.verify_tools(root, args.tools),
        "samples": lambda: agent.samples_command(root, args.action, args.args, args.kind),
    }
    return commands[args.command]()


def main(argv: Sequence[str] | None = None) -> int:
    """Run `setup`. Returns the exit code (2 for a bad command or unknown tool/step)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    tool_ids = {t.id for t in registry.load()}
    try:
        if not argv:
            return ui_launch.launch(REPO_ROOT)
        if argv[0] == NO_UI_FLAG or argv[0] in tool_ids:
            rest = argv[1:] if argv[0] == NO_UI_FLAG else argv
            run_setup(REPO_ROOT, rest[0] if rest else None)
            return 0
        return _dispatch(REPO_ROOT, _parser().parse_args(argv))
    except KeyError as error:
        print(f"setup: error: {error.args[0]}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved; run setup again to carry on.")
        return 130

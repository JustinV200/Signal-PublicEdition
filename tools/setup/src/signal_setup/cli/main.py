"""`setup`: the entry point. With no command it opens the setup window.

  setup [--port N]          the setup wizard in the console window (see cli/ui_launch.py);
                            N is the console's port, stored for its logon step (without
                            --port, the stored one, else 8790)
  setup ui [tool] [--port N]  the same, opened at one tool's steps
  setup --no-ui [tool]      the interactive terminal setup (resumes where it stopped)
  setup <tool>              set up (or redo) one tool in the terminal
  setup step <tool> <step>  run one step in the terminal, nothing else (no wiring);
                            the setup window's "Open a terminal" runs this
  setup auto [tools]        run the picks' automatic steps (required run and copy steps
                            that need nobody), asking nothing; see cli/auto.py
  setup tour [topic]        the guided tour of GUIDE.md (--json: its sections, for the wizard)
  setup status              each tool's platform, status and placeholders left
                            (--json: each tool's health for the console's System tab)
  setup config [tool]       change a tool's settings (--list, --set id=value for the agent)
  setup intro               the intro paragraph (the wizard's first screen)
  setup doc <tool> <step>   print the guide the registry names for a step (read-only;
                            the wizard shows it inline); see cli/doc.py
The rest (list, prereqs, choose, apply, mark, plan, wire, verify, samples) are the
non-interactive commands the setup skill and the wizard call; see cli/agent.py.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from signal_setup import health, platforms, progress, registry, settings
from signal_setup.cli import agent, config, doc, ui_launch
from signal_setup.cli.auto import run_automatic
from signal_setup.intro import intro_text
from signal_setup.ui import run_one_step, run_setup
from signal_setup.ui.tour import run as run_tour
from signal_setup.ui.tour import sections as tour_sections
from signal_setup.wiring import WiringError

NO_UI_FLAG = "--no-ui"
PORT_FLAG = "--port"

# tools/setup/src/signal_setup/cli/main.py -> the repo root is five folders up.
REPO_ROOT = Path(__file__).resolve().parents[5]


def _ids(text: str) -> list[str]:
    """Comma-separated tool ids as a list."""
    return [part.strip() for part in text.split(",") if part.strip()]


def _port(text: str) -> int:
    """A --port value as an int. Raises argparse.ArgumentTypeError outside MIN..MAX_PORT."""
    try:
        return progress.parse_port(text)
    except ValueError as error:
        # ArgumentTypeError, so argparse prints this reason rather than a generic one.
        raise argparse.ArgumentTypeError(str(error)) from error


def _add_port(parser: argparse.ArgumentParser) -> None:
    """The window's --port: the console's port, stored as the `port` answer (None keeps it)."""
    parser.add_argument(
        PORT_FLAG,
        type=_port,
        help=f"the console's port, stored for its logon step "
        f"(default: the stored one, else {progress.DEFAULT_PORT})",
    )


def _window_parser() -> argparse.ArgumentParser:
    """The parser for a bare `setup` with options (only --port)."""
    parser = argparse.ArgumentParser(prog="setup", description="Open the setup window.")
    _add_port(parser)
    return parser


def _parser() -> argparse.ArgumentParser:
    """The parser for every command except the bare `setup` and `setup <tool>`."""
    parser = argparse.ArgumentParser(
        prog="setup",
        description="Set up Signal's tools.",
        # A bare `setup` never reaches this parser, so its help names it here.
        epilog="With no command, `setup [--port N]` opens the setup window; N is the "
        "console's port, stored for its logon step (default: the stored one, else "
        f"{progress.DEFAULT_PORT}). `setup --no-ui [tool]` and `setup <tool>` run the "
        "terminal setup.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").add_argument("--json", action="store_true")
    ui = sub.add_parser("ui")
    ui.add_argument("tool", nargs="?")
    _add_port(ui)
    sub.add_parser("intro")
    guide = sub.add_parser("doc", help="print the guide the registry names for a step")
    guide.add_argument("tool")
    guide.add_argument("step")
    one_step = sub.add_parser("step", help="run one step in the terminal, with no wiring")
    one_step.add_argument("tool")
    one_step.add_argument("step")
    auto = sub.add_parser("auto", help="run the picks' automatic steps, asking nothing")
    auto.add_argument("tools", nargs="?", type=_ids, default=[])
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
        "ui": lambda: ui_launch.launch(root, args.tool, args.port),
        "intro": lambda: print(intro_text()) or 0,
        "doc": lambda: doc.show_guide(root, args.tool, args.step),
        "step": lambda: run_one_step(root, args.tool, args.step),
        "auto": lambda: run_automatic(root, args.tools),
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
    """Run `setup`. Returns the exit code.

    2 for a bad command or unknown tool/step, 1 when wiring left a config file alone
    (or `setup doc` found no guide).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    tool_ids = {t.id for t in registry.load()}
    try:
        if not argv or argv[0].startswith(PORT_FLAG):
            args = _window_parser().parse_args(argv)
            return ui_launch.launch(REPO_ROOT, port=args.port)
        if argv[0] == NO_UI_FLAG or argv[0] in tool_ids:
            rest = argv[1:] if argv[0] == NO_UI_FLAG else argv
            run_setup(REPO_ROOT, rest[0] if rest else None)
            return 0
        return _dispatch(REPO_ROOT, _parser().parse_args(argv))
    except KeyError as error:
        print(f"setup: error: {error.args[0]}", file=sys.stderr)
        return 2
    except WiringError as error:  # a config file setup won't overwrite: one sentence, no trace
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved; run setup again to carry on.")
        return 130

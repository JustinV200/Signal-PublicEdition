"""`whiteboard save | load | saves | delete-save`: keep whole boards and pull them up again.

Each goes through the daemon's /api/saves routes (starting the daemon if needed),
like the board_save / board_load / board_saves / board_delete_save MCP tools.
"""

import argparse
import json

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection, no_arguments
from whiteboard.config import Settings
from whiteboard.saves.meta import REFRESHERS


def add_name_argument(parser: argparse.ArgumentParser) -> None:
    """The positional NAME every save command but `saves` takes."""
    parser.add_argument("name", help="the board's name (or its slug)")


def add_save_arguments(parser: argparse.ArgumentParser) -> None:
    """`save` arguments: NAME, --description, --overwrite, --refresher."""
    add_name_argument(parser)
    parser.add_argument("--description", default="", help="what's on the board, to find it later")
    parser.add_argument("--overwrite", action="store_true", help="replace a save with this name")
    parser.add_argument(
        "--refresher",
        choices=REFRESHERS,
        default="",
        help="what redraws this board from live data (the console's Update button)",
    )


def run_save(args: argparse.Namespace, settings: Settings) -> int:
    """Save the board and print where it went (and why it's scene-only, if it is)."""
    result = daemon_connection(args, settings).call(
        lambda api: api.save_board(args.name, args.description, args.overwrite, args.refresher)
    )
    ink = "with photo and ink" if result.get("has_ink") else "projected items only"
    print(f"saved {result.get('slug')}: {result.get('item_count')} item(s), {ink}")
    print(result.get("folder"))
    if result.get("note"):
        print(result["note"])
    return EXIT_OK


def add_load_arguments(parser: argparse.ArgumentParser) -> None:
    """`load` arguments: NAME, --overlay, --no-ink."""
    add_name_argument(parser)
    parser.add_argument(
        "--overlay", action="store_true", help="add to the current items instead of replacing them"
    )
    parser.add_argument("--no-ink", action="store_true", help="don't project the saved ink")


def run_load(args: argparse.Namespace, settings: Settings) -> int:
    """Put a saved board back and print what was restored."""
    mode = "overlay" if args.overlay else "replace"
    result = daemon_connection(args, settings).call(
        lambda api: api.load_board(args.name, mode, not args.no_ink)
    )
    print(json.dumps(result))
    return EXIT_OK


def run_saves(args: argparse.Namespace, settings: Settings) -> int:
    """Print one line per save, newest first."""
    saves = daemon_connection(args, settings).call(lambda api: api.list_saves())["saves"]
    for meta in saves:
        ink = "ink" if meta.get("has_ink") else "no ink"
        print(
            f"{meta.get('created_at')}  {meta.get('slug')}  ({meta.get('item_count')} items, "
            f"{ink})  {meta.get('name')}: {meta.get('description') or '-'}"
        )
    if not saves:
        print("no saved boards")
    return EXIT_OK


def run_delete_save(args: argparse.Namespace, settings: Settings) -> int:
    """Delete one save."""
    result = daemon_connection(args, settings).call(lambda api: api.delete_save(args.name))
    print(f"deleted {result['deleted'].get('slug')}")
    return EXIT_OK


SAVE = Command(
    "save", "save the board: save NAME [--description] [--overwrite]", add_save_arguments, run_save
)
LOAD = Command(
    "load",
    "bring a saved board back: load NAME [--overlay] [--no-ink]",
    add_load_arguments,
    run_load,
)
SAVES = Command("saves", "list saved boards, newest first", no_arguments, run_saves)
DELETE_SAVE = Command("delete-save", "delete a saved board", add_name_argument, run_delete_save)

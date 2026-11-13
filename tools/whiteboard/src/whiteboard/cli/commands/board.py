"""`whiteboard look | draw | clear`: one-shot board operations through the daemon's API.

Each starts the daemon (detached) if it isn't running, like the MCP tools do.
"""

import argparse
import json

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection, no_arguments
from whiteboard.config import Settings

ITEM_KINDS = ("svg", "mermaid", "text", "markdown", "math", "rough", "image")


def add_look_arguments(parser: argparse.ArgumentParser) -> None:
    """`look` options."""
    parser.add_argument(
        "--raw",
        action="store_true",
        help="skip the board fit: full projector area (or the camera frame if uncalibrated)",
    )
    parser.add_argument(
        "--projection",
        action="store_true",
        help="keep projected items visible instead of blanking them for the photo",
    )


def run_look(args: argparse.Namespace, settings: Settings) -> int:
    """Capture the board and print where the snapshot was saved."""
    clean = not args.projection
    result = daemon_connection(args, settings).call(lambda api: api.look(clean, args.raw))
    print(f"{result['png_path']} ({result.get('width')}x{result.get('height')})")
    if result.get("note"):
        print(result["note"])
    print(f"{len(result.get('items', []))} item(s) projected")
    return EXIT_OK


def add_draw_arguments(parser: argparse.ArgumentParser) -> None:
    """`draw` arguments: KIND CONTENT and the box."""
    parser.add_argument("kind", choices=ITEM_KINDS)
    parser.add_argument("content", help="the item's content (text, Mermaid, SVG, JSON shapes...)")
    for name in ("x", "y", "w", "h"):
        parser.add_argument(f"--{name}", type=float, required=True, help="board pixels")
    parser.add_argument("--id", default="", help="replace the item with this id")
    parser.add_argument("--color", default="", help="e.g. #ffff00")


def run_draw(args: argparse.Namespace, settings: Settings) -> int:
    """Create or replace one item and print its id."""
    item = {"kind": args.kind, "content": args.content}
    item.update(x=args.x, y=args.y, w=args.w, h=args.h)
    if args.id:
        item["id"] = args.id
    if args.color:
        item["style"] = {"color": args.color}
    result = daemon_connection(args, settings).call(lambda api: api.put_item(item))
    print(json.dumps(result.get("item", result)))
    return EXIT_OK


def run_clear(args: argparse.Namespace, settings: Settings) -> int:
    """Remove every projected item."""
    daemon_connection(args, settings).call(lambda api: api.clear())
    print("cleared")
    return EXIT_OK


LOOK = Command(
    "look", "photograph the board and print the snapshot path", add_look_arguments, run_look
)
DRAW = Command(
    "draw", "project one item: draw KIND CONTENT --x --y --w --h", add_draw_arguments, run_draw
)
CLEAR = Command("clear", "remove every projected item", no_arguments, run_clear)

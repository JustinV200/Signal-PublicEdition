"""The `usage` command: `usage show` prints the state file, for debugging."""

import argparse
import sys

from usage.paths import STATE_FILE


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0, or 1 when there's no state file yet.
    """
    parser = argparse.ArgumentParser(prog="usage", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show", help=f"print {STATE_FILE}")
    parser.parse_args(argv)
    try:
        print(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no state yet: {STATE_FILE} (no status line or hook has run)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Entry point for `browser-tool`: load config, wire the real pieces, serve MCP on stdio.

stdout is the MCP protocol channel, so all logging goes to stderr.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from browser_tool.config import ConfigError, load_settings
from browser_tool.gates import DialogConfirmer
from browser_tool.server.app import build_server
from browser_tool.server.check import check_summary
from browser_tool.server.wiring import BACKEND_DOCKER, BACKEND_LOCAL, BACKENDS, build_context

logger = logging.getLogger("browser_tool")

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
EXIT_CONFIG_ERROR = 2


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server until the client disconnects.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    With --check it only loads the config and prints the setup tool's one-line
    {words, fix, command} summary (check.py), then exits.

    Raises:
        SystemExit: With code 2 when the config is invalid, or --check's exit code.
    """
    args = _parse_args(argv)
    if args.check:
        code, summary = check_summary(args.config)
        print(json.dumps(summary))
        raise SystemExit(code)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=LOG_FORMAT)
    try:
        settings = load_settings(args.config)
        confirmer = DialogConfirmer(settings.gates.confirm_timeout_s)
        ctx = build_context(args.backend, settings, confirmer, args.config)
    except (ConfigError, ValueError) as error:
        logger.error("browser-tool cannot start: %s", error)
        raise SystemExit(EXIT_CONFIG_ERROR) from None
    build_server(ctx, is_docker=args.backend == BACKEND_DOCKER).run("stdio")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="browser-tool", description="Browser MCP server (stdio).")
    parser.add_argument(
        "--config", type=Path, default=None, help="config file (default: browser.toml)"
    )
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default=BACKEND_LOCAL,
        help="where Edge runs: the desktop profile (local) or a container per job (docker)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only load the config and print a one-line JSON health summary",
    )
    return parser.parse_args(argv)

"""Lets `python -m claude_sessions` run the CLI; the background daemon is started this way."""

import sys

from claude_sessions.cli import main

sys.exit(main())

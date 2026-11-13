"""`python -m signal_console ...` runs the `console` CLI (how `console open` starts the server)."""

import sys

from signal_console.cli import main

sys.exit(main())

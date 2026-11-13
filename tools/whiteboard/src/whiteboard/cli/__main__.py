"""`python -m whiteboard.cli`: same as the `whiteboard` script.

The MCP server and CLI start the daemon this way (with sys.executable), so it
works without the venv's Scripts folder on PATH.
"""

import sys

from whiteboard.cli.main import main

sys.exit(main())

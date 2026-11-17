"""`python -m analysis_chamber`: the CLI, for the scheduled daemon task (pythonw has no shim)."""

import sys

from analysis_chamber.cli import main

sys.exit(main())

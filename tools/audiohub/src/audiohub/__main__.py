"""Module entry point so `python -m audiohub` behaves like the `audiohub` script."""

import sys

from audiohub.cli import main

if __name__ == "__main__":
    sys.exit(main())

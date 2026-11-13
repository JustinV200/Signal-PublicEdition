"""`python -m mail_digest.assignment_check`: what `assignment-check --now` starts (pythonw)."""

import sys

from mail_digest.assignment_check.cli import main

sys.exit(main())

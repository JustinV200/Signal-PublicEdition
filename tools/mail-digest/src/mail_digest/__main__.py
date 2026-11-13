"""`python -m mail_digest` (the scheduled task runs it under pythonw, with no console)."""

import sys

from mail_digest.digest.cli import main

sys.exit(main())

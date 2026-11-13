"""mail_digest.assignment_check: checker v2, the on-demand read of the owner's course sites.

See README.md and refdocs/research/checker-v2.md. The public API is the CLI entry point
and run_check with its CheckDeps, for tests and other callers.
"""

from mail_digest.assignment_check.cli import main
from mail_digest.assignment_check.run import CheckDeps, CheckOutcome, run_check

__all__ = ["CheckDeps", "CheckOutcome", "main", "run_check"]

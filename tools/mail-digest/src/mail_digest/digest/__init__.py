"""mail_digest.digest: the mail digest's own runner: the `mail-digest` CLI and one run."""

from mail_digest.digest.cli import main
from mail_digest.digest.deps import RunDeps, default_deps
from mail_digest.digest.run import run_once

__all__ = ["RunDeps", "default_deps", "main", "run_once"]

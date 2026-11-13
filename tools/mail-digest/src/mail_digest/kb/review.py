"""Whether a life/ file the KB guard couldn't check has been reviewed since.

Such a file may hold an unchecked digest edit, and the next run's snapshot would take
it as its baseline. So the runner keeps it in the state's needs_review list and
announces it every run until this says it has been reviewed. "Reviewed" is the
README's review step: git shows no uncommitted change to it, because it was
committed after a `git diff life/` or reverted.
"""

from pathlib import Path

from mail_digest.child_env import run_hidden_output

GIT_TIMEOUT_S = 30


def is_reviewed(life_dir: Path, path: str) -> bool:
    """True if git shows life_dir/path as committed and unchanged (or gone and untracked).

    Staged, modified, deleted, untracked and ignored all count as not reviewed, and so
    does anything git can't answer (no git, not a repo, a timeout; logged), so a
    flagged file stays flagged. --literal-pathspecs keeps git from reading `*` or
    `:(...)` in path as a pattern.
    """
    argv = [
        "git", "-C", str(life_dir), "--literal-pathspecs",
        "status", "--porcelain", "--ignored", "--untracked-files=all", "--", path,
    ]  # fmt: skip
    output = run_hidden_output("git status", argv, GIT_TIMEOUT_S)
    return output is not None and not output.strip()

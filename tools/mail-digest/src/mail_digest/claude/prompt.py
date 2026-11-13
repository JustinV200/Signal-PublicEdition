"""Composes the system prompt file of a run that edits life/: its routine, then the shared rules.

The line rules and KB conventions (refdocs/routines/kb-line-rules.md) are the same for
the mail digest and the checker's writer, apart from the tag, so they live in one
file. Just before claude starts, the runner writes routine + rules, with {tag} filled
in, to a file in .state/, and that file is the run's --append-system-prompt-file.
"""

from pathlib import Path

from mail_digest.settings import SHARED_RULES_PATH

TAG_PLACEHOLDER = "{tag}"


def compose_prompt(routine: Path, tag: str, out_path: Path) -> Path:
    """Write routine's text then the shared rules (tag filled in) to out_path; return it.

    Only the shared rules' placeholder is filled in, so a "{tag}" in a routine stays
    as it is. Raises OSError if a file can't be read or written.
    """
    rules = SHARED_RULES_PATH.read_text(encoding="utf-8").replace(TAG_PLACEHOLDER, tag)
    text = routine.read_text(encoding="utf-8").rstrip() + "\n\n" + rules
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return out_path

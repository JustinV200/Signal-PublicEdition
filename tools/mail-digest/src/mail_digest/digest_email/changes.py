"""The lines a digest run added or changed in its editable files, for the digest email.

Read after the KB guard: a file it undid is back to its snapshot and has none, so
what's left is what passed the line rules. The diff is the guard's own
(kb.added_lines).
"""

from pathlib import Path

from mail_digest.kb import added_lines, fold_case


def run_changes(
    life_dir: Path, before: dict[str, bytes], editable: tuple[str, ...]
) -> dict[str, list[str]]:
    """Each editable path (relative to life/) -> its new lines since the snapshot `before`.

    before is the run's snapshot (snapshot(life_dir, editable)), keyed by on-disk
    name, so it's matched ignoring ASCII case as the guard does. Files with no new
    lines are left out. Raises OSError if a file can't be read.
    """
    old = {fold_case(path): content for path, content in before.items()}
    changes = {}
    for path in editable:
        try:
            now = (life_dir / path).read_bytes()
        except FileNotFoundError:
            now = b""  # the guard lets a run delete a file of up to 5 lines
        added = added_lines(_text(old.get(fold_case(path), b"")), _text(now))
        if added:
            changes[path] = added
    return changes


def _text(content: bytes) -> str:
    """A file's bytes as text, as the guard decodes them."""
    return content.decode("utf-8", errors="replace")

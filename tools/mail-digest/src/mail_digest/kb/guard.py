"""The post-run KB guard: undoes digest edits that break the line rules.

Before a run the runner snapshots life/ (snapshot.py). After it, the guard compares
paths ignoring ASCII case (paths.py), because NTFS and Claude Code's Edit rules both
do: an Edit through INBOX.MD is allowed by Edit(/inbox.md), writes inbox.md, and
leaves it renamed INBOX.MD on disk.

- An editable file is the job's work. Its diff must pass the line rules
  (line_rules.py), or it is saved to .state/rejected/ and restored from the
  snapshot. If only its name's case changed, it is renamed back.
- A path under an editable path is the job's work too: the Edit rules match
  gitignore-style, so Edit(/inbox.md) also covers inbox.md/x.md when inbox.md isn't
  a file. Any change there is saved to rejected/ and undone (a new file deleted).
- Any other change is only logged (and announced by the runner). The Edit rules
  mean the job can't have made it, so it's the owner's or another agent's
  concurrent work, and reverting would destroy it.

Every editable path is checked even if one fails. One that can't be checked (an
editable file there but unreadable, or a save, restore or rename that fails) is
listed in GuardReport.failed: its edit is unchecked, and the runner fails the run.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from mail_digest.kb.line_rules import DIGEST_RULES, LineRules, edit_problems
from mail_digest.kb.paths import fold_case, is_covered
from mail_digest.kb.snapshot import snapshot

log = logging.getLogger(__name__)

# Case-folded path relative to life/ -> (its on-disk relative path, its snapshot entry).
# shortcut: two names that differ only in case (a case-sensitive folder) keep the
# last one; NTFS folders are case-insensitive by default, so upgrade only if needed.
type Files = dict[str, tuple[str, bytes]]


@dataclass(frozen=True)
class GuardReport:
    """What the guard found after a run.

    reverted: editable files it restored, and paths under them it undid.
    unexpected: other files that changed during the run (logged, left alone).
    failed: editable paths it couldn't check or undo (logged), so their edits are unchecked.
    """

    reverted: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Check:
    """One guard pass: where life/ and the rejected copies are, and both snapshots."""

    life_dir: Path
    rejected_dir: Path
    before: Files
    after: Files
    rules: LineRules


def guard_edits(
    life_dir: Path,
    before: dict[str, bytes],
    editable: tuple[str, ...],
    rejected_dir: Path,
    rules: LineRules = DIGEST_RULES,
) -> GuardReport:
    """Check this run's edits against the snapshot `before`, and undo the bad ones.

    `before` is snapshot(life_dir, editable) from before the run. A rejected file's
    text is saved to rejected_dir/<path with / as __> before the snapshot is restored
    (a file that didn't exist before is deleted). File errors don't raise: an editable
    path whose file is there but couldn't be read, or couldn't be saved, restored or
    renamed, is logged and listed in `failed`, and the other paths are still checked.
    rules are the line rules for this run's edits (line_rules.LineRules), the digest's
    by default.
    """
    after = snapshot(life_dir, editable)
    check = _Check(life_dir, rejected_dir, _by_folded(before), _by_folded(after), rules)
    reverted, failed = [], []
    for path in editable:
        for step in (_guard_file, _undo_under):
            try:
                reverted += step(check, path)
            except OSError as error:
                log.error("the guard couldn't check or undo %s: %s", path, error)
                failed.append(path)
    unexpected = sorted(
        _name(check, key)
        for key in check.before.keys() | check.after.keys()
        if not is_covered(key, editable) and _is_changed(check, key)
    )
    if unexpected:
        log.warning("files outside the digest's edit list changed during the run: %s", unexpected)
    return GuardReport(
        reverted=tuple(reverted), unexpected=tuple(unexpected), failed=tuple(sorted(set(failed)))
    )


def _guard_file(check: _Check, path: str) -> list[str]:
    """Apply the line rules to one editable file; [path] if it was restored."""
    key = fold_case(path)
    old_name, old = check.before.get(key, (None, None))
    new_name, new = check.after.get(key, (None, None))
    if old_name and not new_name and (check.life_dir / old_name).exists(follow_symlinks=False):
        # The snapshot skips a file it can't read. Taken for deleted (a legal removal
        # of up to 5 lines), whatever the run wrote into it would stay unchecked.
        raise OSError(f"{old_name} is there but couldn't be read")
    problems = edit_problems(_text(old), _text(new), check.rules) if old != new else []
    if problems:
        # Restore through the name the file has now; the rename below fixes the case.
        _undo(check, new_name or old_name, old, "; ".join(problems))
    if old_name and new_name and new_name != old_name:
        _rename_back(check.life_dir, new_name, old_name)
    return [path] if problems else []


def _rename_back(life_dir: Path, new_name: str, old_name: str) -> None:
    """Give a file the digest renamed (only its case changed) its old name again.

    A different file already there under the old name (a case-sensitive folder) is
    left alone and logged: renaming over it would destroy it.
    """
    log.warning("the digest renamed %s to %s; renaming it back", old_name, new_name)
    try:
        (life_dir / new_name).rename(life_dir / old_name)
    except FileExistsError:
        log.warning("not renaming %s back: %s already exists", new_name, old_name)


def _undo_under(check: _Check, path: str) -> list[str]:
    """Undo every change under the editable path `path`; the on-disk paths undone."""
    prefix = fold_case(path) + "/"
    changed = sorted(
        key
        for key in check.before.keys() | check.after.keys()
        if key.startswith(prefix) and _is_changed(check, key)
    )
    names = [_name(check, key) for key in changed]
    for key, name in zip(changed, names, strict=True):
        _undo(check, name, _content(check, key)[0], f"written under {path}, which is one file")
    # The folder at `path` can only have been made during the run (targets are files).
    # Its on-disk name can differ in case (and be several folders where case matters).
    depth = path.count("/") + 1
    for top in {"/".join(name.split("/")[:depth]) for name in names}:
        _remove_empty_folders(check.life_dir / top)
    return names


def _undo(check: _Check, name: str, old: bytes | None, why: str) -> None:
    """Save life/<name>'s current text to rejected/, then put back `old` (None: delete it)."""
    path, rejected = check.life_dir / name, check.rejected_dir / name.replace("/", "__")
    log.warning("undoing the digest's edit to %s (%s); its text is in %s", name, why, rejected)
    rejected.parent.mkdir(parents=True, exist_ok=True)
    rejected.write_bytes(path.read_bytes() if path.is_file() else b"")
    if old is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(old)


def _remove_empty_folders(top: Path) -> None:
    """Remove top and the folders under it, deepest first, if no files are left in them."""
    if not top.is_dir():
        return
    folders = sorted((p for p in top.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts))
    for folder in [*folders, top]:
        if not any(folder.iterdir()):
            folder.rmdir()


def _by_folded(files: dict[str, bytes]) -> Files:
    """A snapshot keyed by case-folded path."""
    return {fold_case(path): (path, content) for path, content in files.items()}


def _content(check: _Check, key: str) -> tuple[bytes | None, bytes | None]:
    """(entry before, entry after) for one case-folded path (None where it didn't exist)."""
    before, after = check.before.get(key), check.after.get(key)
    return (before[1] if before else None), (after[1] if after else None)


def _is_changed(check: _Check, key: str) -> bool:
    """True if the case-folded path changed between the snapshots (or it came or went)."""
    before, after = _content(check, key)
    return before != after


def _name(check: _Check, key: str) -> str:
    """The on-disk path for a case-folded one: its name now, else its name before."""
    return (check.after.get(key) or check.before[key])[0]


def _text(content: bytes | None) -> str:
    """A snapshot entry as text ("" for a file that doesn't exist)."""
    return content.decode("utf-8", errors="replace") if content is not None else ""

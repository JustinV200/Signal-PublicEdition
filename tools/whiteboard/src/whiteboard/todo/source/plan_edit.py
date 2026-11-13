"""set_line_done: tick or untick one todo line in a week plan. The whiteboard's only write to life/.

life/ is the owner's knowledge base and the source of truth for todos. The board
reads it, with one exception: crossing an item out on the board (or an explicit
board_todo_done / board_todo_undone) flips that item's checkbox. This module does
exactly that and nothing else:
- only files named plan.md (the caller passes only this and next week's plans), and
  only inside life/ once links and junctions are resolved;
- only the stored line, matched exactly; if it moved, a unique exact match elsewhere
  in the file is used, otherwise the edit is refused (the owner changed the line);
- only the `[ ]` / `[x]` mark, nothing else on the line or in the file;
- nothing is written if the file changes between reading and writing it, so an
  edit the owner saves meanwhile is never lost.
"""

import re
from pathlib import Path

from whiteboard.shared import FileChangedError
from whiteboard.todo.source.plan_file import PLAN_FILE, PlanText, read_plan, write_plan
from whiteboard.todo.source.plan_lines import SourceLine

_CHECKBOX = re.compile(r"^(?P<lead>\s*[-*+]\s+\[)[ xX](?P<close>\])")
_DONE_MARK = "x"
_OPEN_MARK = " "


class PlanEditError(RuntimeError):
    """The line can't be edited safely: it changed, appears twice, or isn't in a plan."""


def set_line_done(source: SourceLine, is_done: bool, life_dir: Path) -> bool:
    """Set the checkbox on the todo line `source` points at.

    Args:
        source: The line as the last parse saw it.
        is_done: Tick (True) or untick (False).
        life_dir: The owner's KB; the plan must really be inside it.

    Returns:
        True if the file was changed, False if the box already had that mark.

    Raises:
        PlanEditError: Not a plan.md in life/, the line is gone or ambiguous, the file
            changed while it was being edited, or the write failed.
    """
    _check_editable(source.path, life_dir)
    try:
        plan = read_plan(source.path)
    except (OSError, UnicodeDecodeError) as error:
        raise PlanEditError(f"can't read {source.path}: {error}") from error
    lines = plan.lines()
    index = _locate(lines, source)
    body = lines[index].rstrip("\r\n")
    mark = _DONE_MARK if is_done else _OPEN_MARK
    new_body = _CHECKBOX.sub(lambda match: f"{match['lead']}{mark}{match['close']}", body, 1)
    if new_body == body:
        return False
    lines[index] = new_body + lines[index][len(body) :]
    try:
        write_plan(source.path, PlanText("".join(lines), plan.has_bom), plan)
    except FileChangedError as error:
        raise PlanEditError(
            f"{source.path.name} changed while the box was being set, so it was left alone "
            "(try again)"
        ) from error
    except OSError as error:
        raise PlanEditError(f"can't write {source.path}: {error}") from error
    return True


def _check_editable(path: Path, life_dir: Path) -> None:
    """Refuse anything but a plan.md that resolves to a place inside life/.

    Resolving follows symlinks and junctions, so a link under life/terms can't
    point the write at a file elsewhere.

    Raises:
        PlanEditError: It isn't a plan.md, or it's outside life/.
    """
    if path.name != PLAN_FILE:
        raise PlanEditError(f"refusing to edit {path}: only week plans can change")
    if not path.resolve().is_relative_to(life_dir.resolve()):
        raise PlanEditError(f"refusing to edit {path}: it isn't inside {life_dir}")


def _locate(lines: list[str], source: SourceLine) -> int:
    """The index of the stored line: where it was, else its one exact match in the file.

    Raises:
        PlanEditError: The line isn't in the file any more, or is there more than once.
    """

    def body(index: int) -> str:
        return lines[index].rstrip("\r\n")

    if source.line_no < len(lines) and body(source.line_no) == source.text:
        return source.line_no
    matches = [index for index in range(len(lines)) if body(index) == source.text]
    if len(matches) == 1:
        return matches[0]
    problem = "is no longer in" if not matches else f"appears {len(matches)} times in"
    raise PlanEditError(
        f"the todo line {problem} {source.path.name}, so it was left alone "
        f"(the plan changed since it was read; try again): {source.text!r}"
    )

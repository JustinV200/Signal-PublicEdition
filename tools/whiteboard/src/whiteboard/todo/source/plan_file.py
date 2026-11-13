"""Read and write a week plan's text exactly as it is on disk (line endings and BOM kept).

Parsing and the one allowed edit (ticking a checkbox, plan_edit.py) both go through
read_plan, so the line numbers a parse records are the ones an edit finds.
"""

import codecs
from dataclasses import dataclass
from pathlib import Path

from whiteboard.shared import write_atomically

PLAN_FILE = "plan.md"


@dataclass(frozen=True)
class PlanText:
    """A plan file's text, with its line endings, and whether it started with a UTF-8 BOM."""

    text: str
    has_bom: bool

    def lines(self) -> list[str]:
        """The lines with their endings kept (str.splitlines rules, as parse_plan uses)."""
        return self.text.splitlines(keepends=True)


def read_plan(path: Path) -> PlanText:
    """Read a plan as UTF-8.

    Raises:
        OSError: The file can't be read.
        UnicodeDecodeError: It isn't UTF-8.
    """
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    return PlanText(raw[len(codecs.BOM_UTF8) if has_bom else 0 :].decode("utf-8"), has_bom)


def write_plan(path: Path, plan: PlanText, read_as: PlanText) -> None:
    """Write a plan back atomically, with the BOM it had, unless it changed since it was read.

    Args:
        path: The plan file.
        plan: The new text.
        read_as: What read_plan returned; the file must still hold exactly that.

    Raises:
        FileChangedError: Someone else wrote the file after it was read; it's left as is.
        OSError: The file couldn't be replaced.
    """
    write_atomically(path, _encode(plan), unchanged_from=_encode(read_as))


def _encode(plan: PlanText) -> bytes:
    """The bytes on disk for a plan's text (read_plan's exact inverse)."""
    prefix = codecs.BOM_UTF8 if plan.has_bom else b""
    return prefix + plan.text.encode("utf-8")

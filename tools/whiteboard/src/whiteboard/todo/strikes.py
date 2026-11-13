"""Strike geometry: which TODO rows a new line of marker ink crosses out.

The owner crosses an item out on the real board, over its projected row. The change
watcher's clean captures show only ink, in board pixels, the same space the rows
are laid out in. Given the newly added ink (a mask), a row counts as a cross-out
candidate when ink runs through the middle band of the row (not an underline, not
a note above) across most of the row's text, with that ink centred near the row's
middle. A model check then confirms it (daemon/todo/strike_confirm.py), so a stray
mark never completes an item by itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# The middle of a row, as fractions of its height: where a cross-out runs.
BAND_TOP = 0.2
BAND_BOTTOM = 0.8
# A cross-out covers at least this fraction of the item's text width.
MIN_COVERAGE = 0.6
# A very short item ("A18" is about 1.5 em) is measured over at least this many ems
# (42 px at font 21), so a 1 em tick over it covers 0.5, under MIN_COVERAGE.
MIN_SPAN_EM = 2.0
# The new ink over the text has its vertical centre at most this many row heights from
# the row's middle. A line along the row's top or bottom edge, which only grazes the
# band, is usually a neighbouring row's cross-out seen through a slightly-off calibration.
MAX_CENTRE_OFFSET_ROWS = 0.35


@dataclass(frozen=True)
class StrikeTarget:
    """One open row the owner might cross out, in board pixels.

    Attributes:
        id: The item id.
        x0, x1: The text's left and right edge (estimated; see todo.view.layout).
        y0, y1: The row's top and bottom.
        font_px: The item text's font size, which sets the shortest span checked.
        row_x0, row_x1: The whole row's left and right edge (its column), so ink
            beside it (the other column) isn't taken for part of its cross-out.
        text: The row as shown, "[tag] text (due ...)", for the model check to find it by.
        above, below: The rows just above and below it in its column, shown the same
            way ("" if none), so the check can tell two rows with the same text apart.
        has_twin: Whether the row just above or below has the same item text (under
            another tag). A line seen a row off runs through the same words there, so
            a cross-out of this row only gets a "done?" hint.
    """

    id: str
    x0: float
    x1: float
    y0: float
    y1: float
    font_px: float
    row_x0: float
    row_x1: float
    text: str
    above: str = ""
    below: str = ""
    has_twin: bool = False


@dataclass(frozen=True)
class StrikeCandidate:
    """A row that new ink seems to cross out, and what fraction of its text it covers."""

    target: StrikeTarget
    coverage: float


def strike_coverage(added_ink: np.ndarray, target: StrikeTarget) -> float:
    """The fraction of the text's columns that have new ink in the row's middle band.

    Args:
        added_ink: H x W mask (non-zero = ink that wasn't there before), in board px.
        target: The row to check.

    Returns:
        0.0 to 1.0; 0.0 if the row lies outside the mask.
    """
    height, width = added_ink.shape[:2]
    row_h = target.y1 - target.y0
    top = max(0, round(target.y0 + BAND_TOP * row_h))
    bottom = min(height, round(target.y0 + BAND_BOTTOM * row_h))
    left, right, span = _text_columns(target, width)
    if bottom <= top or right <= left:
        return 0.0
    columns_with_ink = np.any(added_ink[top:bottom, left:right], axis=0)
    # Measured against the full span, so ink past the board edge doesn't count.
    return float(np.count_nonzero(columns_with_ink)) / span


def _is_ink_centred(added_ink: np.ndarray, target: StrikeTarget) -> bool:
    """Whether the new ink over the row's text sits near the row's middle.

    Its vertical centre is weighed over the row's whole height, so a line along the
    row's edge counts as off-centre even though it reaches into the band.

    Args:
        added_ink: H x W mask of ink added since the previous capture, in board px.
        target: The row to check.

    Returns:
        True if the centre is within MAX_CENTRE_OFFSET_ROWS row heights of the
        middle; False when it isn't, or there's no new ink over the row.
    """
    height, width = added_ink.shape[:2]
    top, bottom = max(0, round(target.y0)), min(height, round(target.y1))
    left, right, _ = _text_columns(target, width)
    ink_per_line = np.count_nonzero(added_ink[top:bottom, left:right], axis=1)
    if not ink_per_line.any():
        return False
    # + 0.5: pixel line y covers y to y + 1.
    centre_y = top + 0.5 + float(np.average(np.arange(ink_per_line.size), weights=ink_per_line))
    row_h = target.y1 - target.y0
    return abs(centre_y - (target.y0 + target.y1) / 2) <= MAX_CENTRE_OFFSET_ROWS * row_h


def strike_candidates(
    added_ink: np.ndarray, targets: Sequence[StrikeTarget], min_coverage: float = MIN_COVERAGE
) -> list[StrikeCandidate]:
    """The rows that the new ink crosses out (covered enough, and centred), best covered first.

    Args:
        added_ink: H x W mask of ink added since the previous capture.
        targets: The open rows on the board.
        min_coverage: How much of a row's text the ink must cover.
    """
    candidates = [StrikeCandidate(target, strike_coverage(added_ink, target)) for target in targets]
    hits = [
        candidate
        for candidate in candidates
        if candidate.coverage >= min_coverage and _is_ink_centred(added_ink, candidate.target)
    ]
    return sorted(hits, key=lambda candidate: -candidate.coverage)


def _text_columns(target: StrikeTarget, width: int) -> tuple[int, int, int]:
    """(left, right, span) of the row's text: its columns clamped to a `width`-wide mask,
    and its unclamped width in px. That's at least MIN_SPAN_EM ems, so a tick can't
    cover a short item."""
    right_edge = max(target.x1, target.x0 + MIN_SPAN_EM * target.font_px)
    span = round(right_edge) - round(target.x0)
    return max(0, round(target.x0)), min(width, round(right_edge)), span

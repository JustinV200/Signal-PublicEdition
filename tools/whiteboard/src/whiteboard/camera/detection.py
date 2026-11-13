"""Pure frame math for the change watcher: motion between samples, ink between captures.

Motion compares two downscaled, blurred projection-on samples pixel by pixel.
Ink compares two clean captures. Each is reduced to an "ink mask" (pixels clearly
darker than their surroundings), so lighting drift cancels out and only marker
strokes added or erased count. The projector's glare spot isn't ink: its halo only
looks darker than a neighbourhood mean the spot drags up, almost never darker than
the board around it (darker_than_board). Both compares first match the two frames' median
brightness, so auto-exposure and room light shifts don't count. A changed ink blob
also has to change its fine detail (the grey level minus the room light's slow
gradients) by more than the frame's own noise (NOISE_K x the noise), which keeps a
dim room's high-gain noise, flickering faint smudges across the ink threshold, from
reading as new ink, even across a change of lighting.
"""

from dataclasses import dataclass

import cv2
import numpy as np

# Motion samples are shrunk to this width: fast, and immune to pixel noise.
MOTION_WIDTH_PX = 320
BLUR_KERNEL_PX = 5
# adaptiveThreshold neighbourhood (odd), several marker strokes wide.
INK_BLOCK_PX = 31
# Grey levels a pixel must be below its neighbourhood mean to count as ink.
INK_CONTRAST = 12
# darker_than_board's closing side. A dark pixel stops counting only where a whole
# square this size of dark area fits over it, so a mark narrower than this in at least
# one direction (a stroke, a 120x40 filled box) counts, but the middle of a wider dark
# area (a body) doesn't. Replays of the real snapshots report the same pairs at 31 or 61 px,
# but 31 lost filled marks.
BOARD_FILL_PX = 61
# Ink may shift this far between captures (camera wobble) and still be "the same".
ALIGN_TOLERANCE_PX = 2
# Changed-pixel blobs smaller than this are noise, not strokes.
MIN_INK_BLOB_PX = 12
# A changed blob's strongest detail change must beat this many noise sigmas. Noise
# blobs peak at 2-3 sigma; a real stroke's core changes by tens of grey levels.
NOISE_K = 5.0
# Median absolute deviation to standard deviation, for normally distributed noise.
MAD_TO_SIGMA = 1.4826
# Box blur side the noise gate's high-pass takes away: far wider than a stroke, so it
# only removes the room light's slow gradients (a lamp on one side, dusk), which would
# otherwise swell the noise estimate (to 74 grey levels on a real lit-to-dim pair).
LIGHTING_BLUR_PX = 61
# Medians (brightness, noise) are taken on every this-many px each way.
MEDIAN_STEP_PX = 4
# The rectified capture's outer strip flickers between captures where the fit meets
# the board's frame (up to 14 px wide in real snapshots). In the daemon's logs every
# "change" reported from a still board lay in this strip, so ink there isn't counted.
BORDER_NOISE_PX = 16
MASK_ON = 255


@dataclass(frozen=True)
class InkChange:
    """How much ink differs between two clean captures.

    Attributes:
        ratio: Changed ink pixels / all pixels.
        bbox: (x, y, w, h) around the changed ink in image px, or None if nothing changed.
    """

    ratio: float
    bbox: tuple[int, int, int, int] | None


def to_gray(image: np.ndarray) -> np.ndarray:
    """A grayscale copy of a BGR image, or the image itself if already grayscale."""
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def match_brightness(reference: np.ndarray, image: np.ndarray) -> np.ndarray:
    """`image` (grey uint8) scaled so its median brightness matches `reference`'s.

    Auto-exposure and room light scale the whole frame, so matching the medians
    cancels them before differencing. The +1 keeps a black frame from dividing by 0.
    """
    return _scaled(image, _median(reference), _median(image))


def _median(image: np.ndarray) -> float:
    """The median of every MEDIAN_STEP_PX-th pixel each way: the same estimate, far cheaper."""
    return float(np.median(image[::MEDIAN_STEP_PX, ::MEDIAN_STEP_PX]))


def _scaled(image: np.ndarray, target_median: float, image_median: float) -> np.ndarray:
    """`image` scaled from its median to `target_median` (saturating uint8)."""
    gain = (target_median + 1) / (image_median + 1)
    if gain == 1.0:
        return image
    return cv2.convertScaleAbs(image, alpha=gain)


def _matched_pair(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two grey frames at the brighter one's median brightness.

    The darker one is scaled up rather than the brighter one down: scaling down
    shrinks a faint stroke's contrast under INK_CONTRAST, so a real stroke drawn as
    the lights came on would vanish.
    """
    first_median, second_median = _median(first), _median(second)
    if first_median >= second_median:
        return first, _scaled(second, first_median, second_median)
    return _scaled(first, second_median, first_median), second


def motion_frame(image: np.ndarray) -> np.ndarray:
    """Shrink a sample to MOTION_WIDTH_PX wide, grayscale and blurred, for motion_ratio."""
    gray = to_gray(image)
    height, width = gray.shape
    small_size = (MOTION_WIDTH_PX, max(1, round(height * MOTION_WIDTH_PX / width)))
    small = cv2.resize(gray, small_size, interpolation=cv2.INTER_AREA)
    return _blur(small)


def motion_ratio(previous: np.ndarray, current: np.ndarray, pixel_threshold: int) -> float:
    """Fraction of pixels whose grey level moved more than `pixel_threshold`.

    `current` is matched to `previous`'s brightness first, so an exposure change isn't motion.

    Args:
        previous: Earlier motion_frame.
        current: Later motion_frame of the same size.
        pixel_threshold: Grey-level change (0-255) that counts a pixel as moved.
    """
    matched = match_brightness(previous, current)
    return float(np.count_nonzero(cv2.absdiff(previous, matched) > pixel_threshold)) / previous.size


def ink_mask(blurred: np.ndarray) -> np.ndarray:
    """Pixels clearly darker than their neighbourhood and the board around them (MASK_ON).

    That's marker ink, and almost never the halo round the projector's glare spot.

    Args:
        blurred: A grey image already blurred with BLUR_KERNEL_PX.
    """
    mask = cv2.adaptiveThreshold(
        blurred,
        MASK_ON,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        INK_BLOCK_PX,
        INK_CONTRAST,
    )
    mask[~darker_than_board(blurred, INK_CONTRAST)] = 0
    return mask


def darker_than_board(gray: np.ndarray, contrast: int) -> np.ndarray:
    """Pixels more than `contrast` grey levels darker than the board around them (bool).

    The board level is `gray` with its dark marks filled in: a grey closing (max
    filter, then min filter) over a BOARD_FILL_PX square, which fills any dark mark
    that square can't fit inside: a stroke, or a filled box narrower than
    BOARD_FILL_PX in at least one direction (a 120x40 box too). Only where the
    square fits wholly inside a dark area (the middle of a body) is the area left
    unfilled, so it doesn't count; its narrower parts and uneven edge still can. An
    adaptive threshold alone takes the projector's glare spot for ink: the spot
    drags its neighbourhood's mean up, so the fading halo round it reads as darker
    than that mean. But a halo only fades outward, so the closing finds almost no
    brighter board beyond it, and it almost never counts here (a few px of a real
    halo's uneven edge can). A stroke drawn on or beside the halo still counts on a
    lit or dim board, but in pitch dark (median grey under about 20) one within
    about 25 px of the spot loses most of its pixels. The watcher skips dark
    captures anyway, so that only affects dark-room saves.

    Args:
        gray: A grey uint8 image.
        contrast: Grey levels a pixel must be below the board level.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (BOARD_FILL_PX, BOARD_FILL_PX))
    board_level = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    return cv2.subtract(board_level, gray) > contrast


def _blur(gray: np.ndarray) -> np.ndarray:
    """The Gaussian blur every compare starts from (takes the edge off pixel noise)."""
    return cv2.GaussianBlur(gray, (BLUR_KERNEL_PX, BLUR_KERNEL_PX), 0)


def _detail(blurred: np.ndarray) -> np.ndarray:
    """`blurred` (float32) minus its LIGHTING_BLUR_PX box blur: strokes and noise, no room light."""
    grey = blurred.astype(np.float32)
    return grey - cv2.blur(grey, (LIGHTING_BLUR_PX, LIGHTING_BLUR_PX))


def _without_border(mask: np.ndarray) -> np.ndarray:
    """`mask` with its flickering outer BORDER_NOISE_PX strip cleared (in place, and returned)."""
    border = BORDER_NOISE_PX
    mask[:border, :] = 0
    mask[-border:, :] = 0
    mask[:, :border] = 0
    mask[:, -border:] = 0
    return mask


def _real_blobs(mask: np.ndarray, detail_change: np.ndarray) -> np.ndarray:
    """The mask's blobs of at least MIN_INK_BLOB_PX whose peak detail change beats the noise.

    The noise is estimated from the median detail change over the whole frame (robust
    while under half the frame changed). Whole blobs are kept or dropped, so a real
    stroke keeps its full size even where its edges only change a little.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    is_on = labels > 0
    peaks = np.zeros(count, dtype=detail_change.dtype)
    np.maximum.at(peaks, labels[is_on], detail_change[is_on])
    noise_floor = NOISE_K * MAD_TO_SIGMA * _median(detail_change)
    keep = (stats[:, cv2.CC_STAT_AREA] >= MIN_INK_BLOB_PX) & (peaks > noise_floor)
    keep[0] = False  # label 0 is the background
    return np.where(keep[labels], MASK_ON, 0).astype(np.uint8)


def _added_and_erased(
    previous: np.ndarray, current: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ink masks of what was added and erased between two clean captures, and the detail change.

    Ink counts as added where it's in `current` but nowhere near any ink in
    `previous`, and as erased the other way round. That tolerance stops a small
    camera shift from looking like a whole board of new strokes.

    Returns:
        (added, erased, detail_change): the raw masks (blobs not yet filtered) and the
        per-pixel absolute change of _detail after brightness matching and blurring.
    """
    before, after = (_blur(gray) for gray in _matched_pair(to_gray(previous), to_gray(current)))
    before_ink, after_ink = ink_mask(before), ink_mask(after)
    tolerance = cv2.getStructuringElement(
        cv2.MORPH_RECT, (2 * ALIGN_TOLERANCE_PX + 1, 2 * ALIGN_TOLERANCE_PX + 1)
    )
    added = cv2.bitwise_and(after_ink, cv2.bitwise_not(cv2.dilate(before_ink, tolerance)))
    erased = cv2.bitwise_and(before_ink, cv2.bitwise_not(cv2.dilate(after_ink, tolerance)))
    return added, erased, cv2.absdiff(_detail(before), _detail(after))


def added_and_erased_ink(
    previous: np.ndarray, current: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Masks (MASK_ON) of the ink added and the ink erased since `previous`, noise blobs removed.

    Used by the TODO view: added ink shows which rows a new line crosses out (erased
    ink never un-completes an item), and about as much erased ink in the change tells
    old ink that shifted (a camera bump) from a real cross-out.
    """
    added, erased, detail_change = _added_and_erased(previous, current)
    return _real_blobs(added, detail_change), _real_blobs(erased, detail_change)


def added_ink_ratio(previous: np.ndarray, current: np.ndarray) -> float:
    """Fraction of all pixels that is ink added since `previous`, outside BORDER_NOISE_PX.

    The change watcher's large-change check on the live view. Only added ink counts,
    so someone stepping out of the earlier frame doesn't.
    """
    added, _erased = added_and_erased_ink(previous, current)
    return np.count_nonzero(_without_border(added)) / added.size


def ink_change(previous: np.ndarray, current: np.ndarray) -> InkChange:
    """Compare the ink in two clean captures of the same size (BGR or grayscale).

    Both added and erased ink count (see _added_and_erased); the outer
    BORDER_NOISE_PX strip doesn't.
    """
    added, erased, detail_change = _added_and_erased(previous, current)
    changed = _without_border(_real_blobs(cv2.bitwise_or(added, erased), detail_change))
    changed_count = int(np.count_nonzero(changed))
    if changed_count == 0:
        return InkChange(0.0, None)
    x, y, w, h = cv2.boundingRect(changed)
    return InkChange(changed_count / changed.size, (x, y, w, h))

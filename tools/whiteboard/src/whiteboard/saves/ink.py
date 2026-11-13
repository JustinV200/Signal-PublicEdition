"""Pull the owner's marker strokes out of a clean board photo, ready to project back.

The photo is dark ink on a white board. The result is the same strokes on a
transparent background, each in a bright, fully saturated version of its own
colour, because the projector can only add light: black or grey ink becomes
white, a blue marker becomes bright blue. Loading a save projects this image,
so the owner's old drawing reappears on the board. The halo round the
projector's glare spot almost never comes out as ink (see
whiteboard.camera.darker_than_board).
"""

import cv2
import numpy as np

from whiteboard.camera import darker_than_board

# Adaptive threshold: a pixel is ink when it is INK_CONTRAST levels darker than the
# Gaussian-weighted mean of its INK_BLOCK_PX neighbourhood, and than the board around
# it (darker_than_board). Tuned on the real board:
# 15 drops erased-marker ghosting and the board's edges, and keeps faint strokes.
INK_BLOCK_PX = 31
INK_CONTRAST = 15
# Median filter size that removes single-pixel camera noise before thresholding.
DENOISE_PX = 3
# Below this chroma (max - min of B, G, R), ink counts as black or grey and turns
# white. Black marker measures about 5-16 on the webcam; coloured markers far more.
MIN_COLOUR_CHROMA = 40
# A little dilation thickens the strokes so they read well when projected.
_DILATE_KERNEL = np.ones((3, 3), np.uint8)
OPAQUE = 255
FULL = 255


def extract_ink(photo_bgr: np.ndarray) -> np.ndarray:
    """Turn a clean board photo into bright strokes on a transparent background.

    Args:
        photo_bgr: The rectified board photo, uint8 BGR (OpenCV order).

    Returns:
        A uint8 BGRA image of the same size (OpenCV order; a PNG of it is RGBA):
        stroke pixels are opaque and bright, everything else is fully transparent.
    """
    gray = cv2.medianBlur(cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2GRAY), DENOISE_PX)
    is_ink = (
        cv2.adaptiveThreshold(
            gray,
            FULL,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            INK_BLOCK_PX,
            INK_CONTRAST,
        )
        > 0
    ) & darker_than_board(gray, INK_CONTRAST)
    bright = _bright_colours(cv2.medianBlur(photo_bgr, DENOISE_PX))
    ink = np.zeros((*gray.shape, 4), np.uint8)
    ink[is_ink, :3] = bright[is_ink]
    ink[is_ink, 3] = OPAQUE
    # Dilating the colour image (not just the mask) grows each stroke in its own
    # colour; the photo's paler stroke edges would otherwise come out white.
    return cv2.dilate(ink, _DILATE_KERNEL)


def encode_png(image: np.ndarray) -> bytes:
    """Encode a BGR or BGRA image as PNG bytes (for photo.png and ink.png).

    Raises:
        OSError: OpenCV couldn't encode it.
    """
    is_ok, png = cv2.imencode(".png", image)
    if not is_ok:
        raise OSError("could not encode image as PNG")
    return png.tobytes()


def _bright_colours(image_bgr: np.ndarray) -> np.ndarray:
    """Every pixel's hue at full brightness: saturated if it has colour, else white."""
    channels = image_bgr.astype(np.int16)
    chroma = channels.max(axis=2) - channels.min(axis=2)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = np.where(chroma >= MIN_COLOUR_CHROMA, FULL, 0)
    hsv[..., 2] = FULL
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

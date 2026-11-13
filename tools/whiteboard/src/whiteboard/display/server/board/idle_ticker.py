"""Where the idle view's news ticker scrolls, as a fraction of the board, for the camera.

The ticker is the one part of any page that moves on its own all the time. The change
watcher compares live frames for motion, so BoardController.motion_masks hands it this
band to leave out (the idle page draws at DESIGN size, scaled and centred on the stage
like static/idle/idle.js fitIdle does). Clean captures blank the whole page anyway, so
ink in the band still counts once anything else makes a capture due.
"""

from whiteboard.shared import FractionBox

# The idle page's design size (static/idle/layout.js DESIGN).
DESIGN_WIDTH, DESIGN_HEIGHT = 1112, 720
# The NEWS footer (layout.js LAYOUT.news: 40, 652, 1032 x 28) plus 12 px all round, for
# the projector's blur and a slightly-off fit. tests/display/server/test_idle_ticker.py
# checks it still covers layout.js.
TICKER_BAND = (28, 640, 1056, 52)


def ticker_band_fraction(stage_width: float, stage_height: float) -> FractionBox:
    """The ticker band as (x, y, w, h) fractions of a stage this size.

    Args:
        stage_width: The stage's logical width (BoardController.stage()), > 0.
        stage_height: Its logical height, > 0.
    """
    scale = min(stage_width / DESIGN_WIDTH, stage_height / DESIGN_HEIGHT)
    left = (stage_width - DESIGN_WIDTH * scale) / 2
    top = (stage_height - DESIGN_HEIGHT * scale) / 2
    x, y, width, height = TICKER_BAND
    return (
        (left + x * scale) / stage_width,
        (top + y * scale) / stage_height,
        width * scale / stage_width,
        height * scale / stage_height,
    )

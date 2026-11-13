"""FractionBox: a box given as fractions of an image or board, so it fits any resolution.

The display side says where the board moves by itself (BoardController.motion_masks)
and the camera side leaves it out of its live view (camera.watcher), each at its own size.
"""

# (x, y, w, h) as fractions (0 to 1) of the width and height.
FractionBox = tuple[float, float, float, float]

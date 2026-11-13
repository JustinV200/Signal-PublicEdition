"""Public API of whiteboard.shared: small helpers used by several whiteboard packages.

- `write_atomically`, `FileChangedError` (files.py): replace a file in one step.
- `FractionBox` (boxes.py): an (x, y, w, h) box as fractions of the width and height.
"""

from whiteboard.shared.boxes import FractionBox
from whiteboard.shared.files import FileChangedError, write_atomically

__all__ = ["FileChangedError", "FractionBox", "write_atomically"]

"""Line-level readers and writers for the config formats setup edits.

Each format module has the same four functions:
  read(text, key)            the key's current value (str, int, float, bool, list), or None
  write(text, key, literal)  `text` with the key set to `literal`, comments kept
  entries(text)              every (key, value) pair, for the placeholder scan
  literal(value)             a Python value written the way the format spells it
Texts are newline-separated; the store handles CRLF files. AGENTS.md holds its settings
inside prose, so it's read with md_marked (by name) instead of md_lines.
"""

from pathlib import Path
from types import ModuleType

from signal_setup.settings.formats import md_lines, md_marked, psd1_lines, toml_lines

_BY_SUFFIX = {".toml": toml_lines, ".psd1": psd1_lines, ".md": md_lines}
# Files whose settings sit in prose, marked with <!-- setting:key --> comments.
_BY_NAME = {"AGENTS.md": md_marked}


def for_path(path: str | Path) -> ModuleType:
    """The format module for a file, by its suffix. Raises ValueError for an unknown one."""
    if Path(path).name in _BY_NAME:
        return _BY_NAME[Path(path).name]
    suffix = Path(path).suffix
    if suffix not in _BY_SUFFIX:
        raise ValueError(f"setup can't edit {suffix} files ({path})")
    return _BY_SUFFIX[suffix]

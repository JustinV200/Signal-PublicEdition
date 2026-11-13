"""Well-known filesystem locations for the browser tool, and telling a network path apart.

Paths are derived from this file's location inside the source tree
(tools/browser/src/browser_tool/config/paths.py). That holds because uv installs
the project in editable mode; a non-editable install would break these paths.
"""

import ctypes
import os
from pathlib import Path

# GetDriveTypeW's answer for a mapped network drive.
DRIVE_REMOTE = 4

# parents: [0] config, [1] browser_tool, [2] src, [3] tools/browser
TOOL_ROOT: Path = Path(__file__).resolve().parents[3]

# Optional per-machine config. Gitignored; see browser.example.toml.
DEFAULT_CONFIG_PATH: Path = TOOL_ROOT / "browser.toml"


def resolve_tool_path(value: str) -> Path:
    """Turn a config path into an absolute path.

    Args:
        value: An absolute path, or a path relative to the tool root (tools/browser).

    Returns:
        The absolute path. Nothing is created or checked on disk.
    """
    path = Path(value)
    return path if path.is_absolute() else TOOL_ROOT / path


def is_network_path(path: Path) -> bool:
    r"""True for a UNC path (\\server\share) or a path on a mapped network drive.

    Reading a file there would open an SMB connection (and leak an NTLM
    handshake), so the loader refuses such folders. Lexical apart from
    GetDriveTypeW, which asks Windows about the drive letter only.
    """
    drive = os.path.splitdrive(os.path.abspath(path))[0]
    if not drive.endswith(":"):  # a UNC share, or no drive at all
        return True
    return _drive_type(drive + "\\") == DRIVE_REMOTE


def _drive_type(root: str) -> int:
    """GetDriveTypeW for a drive root, such as C: and a backslash."""
    return ctypes.windll.kernel32.GetDriveTypeW(root)

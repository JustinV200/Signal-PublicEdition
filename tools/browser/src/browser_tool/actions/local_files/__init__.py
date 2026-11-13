"""Public API of browser_tool.actions.local_files: checking and reading one local file.

read_checked_file (checked_read.py) is the one path check upload_file and
read_download share: a plain drive path inside the given folders, no link,
junction or short name on the way, never the vault, a profile, .env or key
file, read once into memory. Pure: no browser.
"""

from browser_tool.actions.local_files.checked_read import CheckedFile, read_checked_file

__all__ = ["CheckedFile", "read_checked_file"]

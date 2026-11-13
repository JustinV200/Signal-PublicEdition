"""Public API of browser_tool.actions.uploads: the upload_file tool.

upload.py is the tool (gating, file input or picker); the local file is
checked and read by actions.local_files.
"""

from browser_tool.actions.uploads.upload import upload_file

__all__ = ["upload_file"]

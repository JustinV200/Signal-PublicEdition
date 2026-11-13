"""Public API of browser_tool.downloads: saving the desktop browser's downloads safely."""

from browser_tool.downloads.file_names import reserve_path, safe_file_name
from browser_tool.downloads.incoming import INCOMING_FOLDER_NAME, clear_folder
from browser_tool.downloads.recorder import DownloadRecorder, SavedDownload

__all__ = [
    "INCOMING_FOLDER_NAME",
    "DownloadRecorder",
    "SavedDownload",
    "clear_folder",
    "reserve_path",
    "safe_file_name",
]

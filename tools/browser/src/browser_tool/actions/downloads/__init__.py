"""Public API of browser_tool.actions.downloads: what the model learns about downloads.

notes.py adds "download saved" notes to every tool result; read_download.py
is the read_download tool, which reads a saved PDF (pdf_text.py, which runs
pdf_worker.py in a child process) or plain-text file from the downloads folder.
"""

from browser_tool.actions.downloads.notes import download_notes
from browser_tool.actions.downloads.read_download import read_download

__all__ = ["download_notes", "read_download"]

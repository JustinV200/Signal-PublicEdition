"""Public API of browser_tool.session.dialogs: the page dialogs a tab is waiting on.

watch.py holds them (DialogWatch); race.py runs browser work that a dialog
could freeze without hanging on it; file_chooser.py stops native file pickers.
"""

from browser_tool.session.dialogs.file_chooser import FileChooserWatch
from browser_tool.session.dialogs.race import (
    STOPPED_BY_DIALOG,
    act_until_dialog,
    read_until_dialog,
    run_unless_dialog,
)
from browser_tool.session.dialogs.watch import (
    MAX_MESSAGE_CHARS,
    AlertNote,
    DialogWatch,
    PendingDialog,
)

__all__ = [
    "MAX_MESSAGE_CHARS",
    "STOPPED_BY_DIALOG",
    "AlertNote",
    "DialogWatch",
    "FileChooserWatch",
    "PendingDialog",
    "act_until_dialog",
    "read_until_dialog",
    "run_unless_dialog",
]

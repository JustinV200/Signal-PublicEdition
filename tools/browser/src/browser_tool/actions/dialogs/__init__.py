"""Public API of browser_tool.actions.dialogs: answering page dialogs, and noting them.

answer_dialog (answer.py) accepts or dismisses the dialog that freezes the
current tab; dialog_notes (notes.py) is what the tool runner adds to every
result about alerts, file pickers and open dialogs.
"""

from browser_tool.actions.dialogs.answer import answer_dialog
from browser_tool.actions.dialogs.notes import dialog_notes

__all__ = ["answer_dialog", "dialog_notes"]

"""Public API of signal_confirm: ask the owner Allow/Deny in a hardened dialog.

The dialog runs in a short-lived child process, so confirm() is safe from any
thread and confirm_async() never blocks an event loop. Importing this package
does not load tkinter; only the child does.
"""

from signal_confirm.launcher import confirm, confirm_async
from signal_confirm.sanitize import elide, sanitize_text

__all__ = ["confirm", "confirm_async", "elide", "sanitize_text"]

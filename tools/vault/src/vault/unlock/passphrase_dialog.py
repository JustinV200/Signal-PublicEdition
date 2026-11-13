"""Native masked passphrase dialog (tkinter), used by the passphrase unlock fallback.

A GUI dialog rather than a terminal prompt, because fills happen inside the
browser tool's process, which has no terminal the owner can type into. The
dialog is topmost, masks input, and cancels itself after a timeout so a fill
never hangs forever.
"""

import gc
import tkinter as tk
from dataclasses import dataclass

DIALOG_TITLE = "Signal vault"
MASK_CHARACTER = "\u2022"
DEFAULT_TIMEOUT_S = 120
ENTRY_WIDTH_CHARS = 40
PADDING_PX = 10


@dataclass(frozen=True)
class PassphraseRequest:
    """What to ask for.

    Attributes:
        message: The explanation shown above the field.
        confirm: Ask twice and require both entries to match (for `vault init`).
        timeout_s: Seconds before the dialog cancels itself.
        min_length: Minimum length in characters; shorter entries are refused in the dialog.
    """

    message: str
    confirm: bool = False
    timeout_s: int = DEFAULT_TIMEOUT_S
    min_length: int = 0


class _PassphraseDialog:
    """One dialog instance; `run()` blocks until OK, Cancel or timeout."""

    def __init__(self, request: PassphraseRequest) -> None:
        self._request = request
        self._result: bytearray | None = None
        self._root = tk.Tk()
        self._root.title(DIALOG_TITLE)
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._cancel)
        tk.Label(self._root, text=request.message, justify="left").pack(
            padx=PADDING_PX, pady=PADDING_PX
        )
        labels = ["Passphrase", "Type it again"] if request.confirm else ["Passphrase"]
        self._entries = [self._add_entry(label) for label in labels]
        tk.Label(self._root, text=f"Cancels itself after {request.timeout_s} seconds.").pack()
        # Errors are plain text, so they don't rely on the red alone.
        self._error = tk.Label(self._root, text="", fg="red")
        self._error.pack()
        self._add_buttons()
        self._root.bind("<Return>", lambda _event: self._submit())
        self._root.bind("<Escape>", lambda _event: self._cancel())
        self._root.after(request.timeout_s * 1000, self._cancel)

    def _add_entry(self, label: str) -> tk.Entry:
        tk.Label(self._root, text=label).pack(padx=PADDING_PX, anchor="w")
        entry = tk.Entry(self._root, show=MASK_CHARACTER, width=ENTRY_WIDTH_CHARS)
        entry.pack(padx=PADDING_PX, pady=2)
        return entry

    def _add_buttons(self) -> None:
        row = tk.Frame(self._root)
        row.pack(pady=PADDING_PX)
        tk.Button(row, text="OK", width=10, command=self._submit).pack(side="left", padx=4)
        tk.Button(row, text="Cancel", width=10, command=self._cancel).pack(side="left", padx=4)

    def _submit(self) -> None:
        values = [entry.get() for entry in self._entries]
        if len(set(values)) != 1:
            self._reject("The passphrases don't match.")
            return
        if len(values[0]) < self._request.min_length:
            self._reject(f"Use at least {self._request.min_length} characters.")
            return
        self._result = bytearray(values[0].encode("utf-8"))
        self._root.destroy()

    def _reject(self, message: str) -> None:
        """Show `message`, clear every entry and put focus back on the first."""
        self._error.config(text=message)
        for entry in self._entries:
            entry.delete(0, tk.END)
        self._entries[0].focus_set()

    def _cancel(self) -> None:
        self._result = None
        self._root.destroy()

    def run(self) -> bytearray | None:
        self._root.lift()
        self._root.focus_force()
        self._entries[0].focus_set()
        self._root.mainloop()
        # Drop every Tk reference here, on the thread that created the
        # interpreter. If one were freed later on another thread, Tcl aborts the
        # whole process ("async handler deleted by the wrong thread").
        self._root = None
        self._entries = []
        self._error = None
        gc.collect()
        return self._result


def ask_passphrase(request: PassphraseRequest) -> bytearray | None:
    """Show the dialog and block until the owner answers.

    Must run on a thread that owns no other Tk interpreter (the vault calls it
    through `asyncio.to_thread`).

    Args:
        request: The message, whether to confirm, and the timeout.

    Returns:
        The passphrase as UTF-8 bytes in a bytearray (caller wipes it), or None
        if the owner cancelled or the dialog timed out.
    """
    return _PassphraseDialog(request).run()

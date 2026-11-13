"""The Allow/Deny window (tkinter). Runs only inside the child process started by launcher.py.

Built so stray input can't approve:
- Deny has the focus and is the default button.
- Allow starts disabled and only works once the window has been shown for the arm delay.
- Allow has no keyboard shortcut and is left out of the focus order, so Tab can't reach
  it: Return and Space press only the focused button, which is always Deny. Only a
  deliberate click approves.
- Escape, closing the window, the timeout and any error inside a Tk callback all deny.
"""

import time
import tkinter as tk
import traceback
from tkinter import ttk

from signal_confirm.arming import is_armed
from signal_confirm.protocol import DialogRequest
from signal_confirm.sanitize import sanitize_message, sanitize_text

MAX_TITLE_CHARS = 100
MAX_MESSAGE_CHARS = 2000
TEXT_WIDTH_CHARS = 72
# Taller messages scroll, so the buttons always stay on screen.
MAX_TEXT_LINES = 20
PADDING_PX = 12
MS_PER_SECOND = 1000


def show_dialog(request: DialogRequest) -> bool:
    """Show the dialog for `request` and block until it is answered.

    Returns:
        True only when the owner clicked an armed Allow.

    Raises:
        tk.TclError: If Tk can't start (e.g. no desktop session).
    """
    return ConfirmDialog(request).run()


class ConfirmDialog:
    """One topmost, centred Allow/Deny window."""

    def __init__(self, request: DialogRequest) -> None:
        """Build the window (not shown until run()).

        Raises:
            tk.TclError: If Tk can't start.
        """
        self._request = request
        self._answer: bool | None = None
        self._shown_at_s: float | None = None
        self._root = tk.Tk()
        self._root.report_callback_exception = self._fail_closed
        self._build_window()

    def run(self) -> bool:
        """Show the window, wait for an answer or the timeout, and return True only for Allow."""
        timeout_ms = int(self._request.timeout_s * MS_PER_SECOND)
        self._root.after(timeout_ms, self._finish, False)
        self._root.mainloop()
        self._root.destroy()
        return self._answer is True

    def _build_window(self) -> None:
        """Lay out the message and buttons and wire the keys."""
        root = self._root
        root.title(sanitize_text(self._request.title, MAX_TITLE_CHARS))
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", lambda: self._finish(False))
        frame = ttk.Frame(root, padding=PADDING_PX)
        frame.pack(fill="both", expand=True)
        self._build_message(frame)
        self._build_buttons(frame)
        root.bind("<Escape>", lambda _event: self._finish(False))
        # Space already presses the focused ttk button; make Return do the same, nothing more.
        root.bind("<Return>", self._press_focused_button)
        root.bind("<Map>", self._on_map)
        # Tk's own helper: withdraw, measure, centre on the screen, show.
        root.eval("tk::PlaceWindow . center")

    def _build_message(self, parent: ttk.Frame) -> None:
        """Add the sanitized message as read-only, scrollable text."""
        message = sanitize_message(self._request.message, MAX_MESSAGE_CHARS)
        box = ttk.Frame(parent)
        box.pack(fill="both", expand=True)
        text = tk.Text(
            box,
            width=TEXT_WIDTH_CHARS,
            height=min(MAX_TEXT_LINES, _estimate_lines(message)),
            wrap="word",
            relief="flat",
            font="TkDefaultFont",
            takefocus=False,
        )
        scrollbar = ttk.Scrollbar(box, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", message)
        text.configure(state="disabled")
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

    def _build_buttons(self, parent: ttk.Frame) -> None:
        """Add Allow (disabled, out of the focus order) and Deny (focused, default)."""
        row = ttk.Frame(parent, padding=(0, PADDING_PX, 0, 0))
        row.pack(fill="x")
        self._deny = ttk.Button(
            row, text="Deny", default="active", command=lambda: self._finish(False)
        )
        self._allow = ttk.Button(
            row, text="Allow", state="disabled", takefocus=False, command=self._on_allow
        )
        self._deny.pack(side="right")
        self._allow.pack(side="right", padx=(0, PADDING_PX))

    def _on_map(self, event: tk.Event) -> None:
        """When the window itself first appears: focus Deny and start the arm delay."""
        # <Map> bound on the root also fires for each child widget; only the window counts.
        if event.widget is not self._root or self._shown_at_s is not None:
            return
        self._shown_at_s = time.monotonic()
        # Focus set before the window is shown doesn't stick, so it is set here.
        self._deny.focus_set()
        self._root.after(int(self._request.arm_delay_s * MS_PER_SECOND), self._enable_allow)

    def _enable_allow(self) -> None:
        """Let Allow be clicked once the arm delay has passed."""
        self._allow.state(["!disabled"])

    def _on_allow(self) -> None:
        """Approve, but only if armed: the clock is checked, not just the button state."""
        if is_armed(self._shown_at_s, time.monotonic(), self._request.arm_delay_s):
            self._finish(True)

    def _press_focused_button(self, event: tk.Event) -> None:
        """Return key: press the focused button (only Deny can have the focus)."""
        if isinstance(event.widget, ttk.Button):
            event.widget.invoke()

    def _finish(self, is_allowed: bool) -> None:
        """Record the first answer and leave the event loop."""
        if self._answer is None:
            self._answer = is_allowed
        self._root.quit()

    def _fail_closed(self, *exc_info: object) -> None:
        """Tk callback error: print it for the parent's log and deny."""
        traceback.print_exception(*exc_info)
        self._answer = False
        self._root.quit()


def _estimate_lines(message: str) -> int:
    """Roughly how many lines `message` wraps to at TEXT_WIDTH_CHARS (at least 1 per line)."""
    return sum(max(1, -(-len(line) // TEXT_WIDTH_CHARS)) for line in message.split("\n"))

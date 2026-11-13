"""InputHooks: low-level keyboard and mouse hooks that report each input event to the keeper.

WH_KEYBOARD_LL and WH_MOUSE_LL see keyboard and mouse input before any window does, and
the keyboard hook gets each key's virtual-key code, so the keeper can tell a typed key
from a media key a Bluetooth headset sent. The mouse hook tells a move (with the cursor's
position, so the keeper can ignore jitter) from a click or the wheel. Input another
program sent (SendInput, keybd_event, remote tools) carries an "injected" flag, and only
goes to on_injected: just the owner's own keyboard and mouse may wake sleep mode.
sleepmode.keeper.input_watch decides what counts.
Windows calls the hooks on the thread that installed them while it pumps messages
(sleepmode.keeper.message_loop), so the callbacks only report the event and return.
The hooks never block or change any input.
"""

import ctypes
import functools
import logging
from collections.abc import Callable
from ctypes import wintypes

log = logging.getLogger(__name__)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0  # the only hook code that carries an event
LLKHF_UP = 0x80  # KBDLLHOOKSTRUCT.flags bit set on a key release
# The "injected" flags; the lower-integrity variants (0x02) always come with these set.
LLKHF_INJECTED = 0x10  # KBDLLHOOKSTRUCT.flags: a key another program sent
LLMHF_INJECTED = 0x01  # MSLLHOOKSTRUCT.flags: a mouse event another program sent
WM_MOUSEMOVE = 0x0200  # the mouse hook's wparam for a move; anything else is a button or wheel

_LRESULT = ctypes.c_ssize_t
_HOOKPROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# on_input(vk_code, is_key_up): a key's virtual-key code, or None for a mouse button or
# the wheel, and whether it's a key release (always False for the mouse).
OnInput = Callable[[int | None, bool], None]
# on_mouse_move(x, y): the cursor's new screen position.
OnMouseMove = Callable[[int, int], None]
# on_injected(): one keyboard or mouse event another program sent.
OnInjected = Callable[[], None]


class _KeyboardEvent(ctypes.Structure):
    """KBDLLHOOKSTRUCT, what the keyboard hook's lparam points at."""

    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseEvent(ctypes.Structure):
    """MSLLHOOKSTRUCT, what the mouse hook's lparam points at."""

    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class InputHooks:
    """The keyboard and mouse hooks, installed for the calling thread until close()."""

    def __init__(
        self, on_input: OnInput, on_mouse_move: OnMouseMove, on_injected: OnInjected
    ) -> None:
        """Install both hooks.

        Args:
            on_input: Called for each key press, auto-repeat or release with its
                virtual-key code and whether it's a release, and with (None, False) for
                each mouse button or wheel event. It runs inside the hook, so it must be
                quick.
            on_mouse_move: Called for each mouse move with the cursor's x and y; just as
                quick.
            on_injected: Called instead of the other two for each injected event (one
                another program sent), with no arguments; just as quick.

        Raises:
            OSError: A hook couldn't be installed. Neither is left installed then.
        """
        self._user32 = _user32()
        self._on_input = on_input
        self._on_mouse_move = on_mouse_move
        self._on_injected = on_injected
        # Kept on the instance: ctypes must not free the callbacks while Windows calls them.
        self._keyboard_proc = _HOOKPROC(self._on_keyboard)
        self._mouse_proc = _HOOKPROC(self._on_mouse)
        self._handles: list[int] = []
        try:
            self._install(WH_KEYBOARD_LL, self._keyboard_proc)
            self._install(WH_MOUSE_LL, self._mouse_proc)
        except OSError:
            self.close()
            raise

    def close(self) -> None:
        """Remove the hooks. Safe to call twice."""
        for handle in self._handles:
            # FALSE here is expected for a hook Windows already removed itself (one that
            # ran too slow), so the result isn't checked.
            self._user32.UnhookWindowsHookEx(handle)
        self._handles.clear()

    def _install(self, hook_id: int, proc: object) -> None:
        # Low-level hooks run in this process, never injected, so they need no module handle.
        handle = self._user32.SetWindowsHookExW(hook_id, proc, None, 0)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handles.append(handle)

    def _on_keyboard(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            event = ctypes.cast(lparam, ctypes.POINTER(_KeyboardEvent)).contents
            if event.flags & LLKHF_INJECTED:
                self._report(self._on_injected)
            else:
                self._report(self._on_input, event.vkCode, bool(event.flags & LLKHF_UP))
        return self._user32.CallNextHookEx(None, code, wparam, lparam)

    def _on_mouse(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            event = ctypes.cast(lparam, ctypes.POINTER(_MouseEvent)).contents
            if event.flags & LLMHF_INJECTED:
                self._report(self._on_injected)
            elif wparam == WM_MOUSEMOVE:
                self._report(self._on_mouse_move, event.pt.x, event.pt.y)
            else:
                self._report(self._on_input, None, False)
        return self._user32.CallNextHookEx(None, code, wparam, lparam)

    def _report(self, callback: Callable[..., None], *args: int | bool | None) -> None:
        try:
            callback(*args)
        except Exception:
            # Raising out of a hook would skip CallNextHookEx, and the keeper's stderr goes
            # nowhere, so log it here instead.
            log.exception("the input hook's callback failed")


@functools.cache
def _user32() -> ctypes.WinDLL:
    """user32 with the signatures this file calls (64-bit handles need explicit types)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int,
        _HOOKPROC,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    ]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.CallNextHookEx.argtypes = [
        wintypes.HHOOK,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.CallNextHookEx.restype = _LRESULT
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    return user32

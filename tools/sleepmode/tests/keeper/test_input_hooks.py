"""Tests for how the input hooks route each event: injected input only to on_injected.

Real hooks can't be installed in a test, so a fake user32 stands in and the tests call
the hook procedures directly with the structs Windows would pass.
"""

import ctypes
from ctypes import wintypes

import pytest

from sleepmode.keeper import input_hooks
from sleepmode.keeper.input_hooks import InputHooks

VK_A = 0x41
WM_LBUTTONDOWN = 0x0201


class FakeUser32:
    """Stands in for user32: installing a hook always works, the rest does nothing."""

    def SetWindowsHookExW(self, *_args) -> int:  # noqa: N802 (the Win32 name)
        return 1

    def CallNextHookEx(self, *_args) -> int:  # noqa: N802
        return 0

    def UnhookWindowsHookEx(self, *_args) -> int:  # noqa: N802
        return 0


def _keyboard(hooks: InputHooks, flags: int) -> None:
    event = input_hooks._KeyboardEvent(VK_A, 0, flags, 0, 0)
    hooks._on_keyboard(input_hooks.HC_ACTION, 0, ctypes.addressof(event))


def _mouse(hooks: InputHooks, flags: int, wparam: int) -> None:
    event = input_hooks._MouseEvent(wintypes.POINT(5, 6), 0, flags, 0, 0)
    hooks._on_mouse(input_hooks.HC_ACTION, wparam, ctypes.addressof(event))


@pytest.mark.parametrize(
    ("send", "expected"),
    [
        (lambda h: _keyboard(h, 0x10), ("injected",)),  # LLKHF_INJECTED
        (lambda h: _keyboard(h, 0x12), ("injected",)),  # ...from a lower integrity level
        (lambda h: _keyboard(h, 0x00), ("input", VK_A, False)),  # a real press
        (lambda h: _keyboard(h, 0x80), ("input", VK_A, True)),  # a real release
        (lambda h: _mouse(h, 0x01, WM_LBUTTONDOWN), ("injected",)),  # LLMHF_INJECTED
        (lambda h: _mouse(h, 0x03, input_hooks.WM_MOUSEMOVE), ("injected",)),  # lower IL
        (lambda h: _mouse(h, 0x00, input_hooks.WM_MOUSEMOVE), ("move", 5, 6)),  # a real move
        (lambda h: _mouse(h, 0x00, WM_LBUTTONDOWN), ("input", None, False)),  # a real click
    ],
)
def test_only_real_input_reaches_on_input_and_on_mouse_move(monkeypatch, send, expected) -> None:
    monkeypatch.setattr(input_hooks, "_user32", FakeUser32)
    calls = []
    hooks = InputHooks(
        lambda vk, is_up: calls.append(("input", vk, is_up)),
        lambda x, y: calls.append(("move", x, y)),
        lambda: calls.append(("injected",)),
    )
    send(hooks)
    assert calls == [expected]

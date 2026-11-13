"""Tests for which input wakes sleep mode: the key table, mouse jitter, the grace and fallbacks.

The real hooks can't run in a test, so FakeHooks hands each test the callback they'd call.
"""

import logging

import pytest

from sleepmode.config import InputSettings
from sleepmode.keeper.input_watch import InputWatch, is_real_input


class FakeHooks:
    """Stands in for InputHooks; `installed` lists every set, oldest first."""

    installed: list["FakeHooks"]

    def __init__(self, on_input, on_mouse_move, on_injected) -> None:
        self.on_input = on_input
        self.on_mouse_move = on_mouse_move
        self.on_injected = on_injected
        self.is_closed = False
        FakeHooks.installed.append(self)

    def close(self) -> None:
        self.is_closed = True


def NOTHING_DOWN(_vk: int) -> bool:  # noqa: N802 (reads as a constant)
    return False


@pytest.fixture(autouse=True)
def _fresh_hooks() -> None:
    FakeHooks.installed = []


@pytest.mark.parametrize(
    ("vk_code", "is_real"),
    [
        (None, True),  # a mouse button or the wheel
        (0x41, True),  # A
        (0x13, True),  # Pause/Break, a keyboard key, not VK_MEDIA_PLAY_PAUSE
        (0xA5, True),  # VK_RMENU, just below the media block
        (0xB8, True),  # reserved, just above it
        (0xA6, False),  # VK_BROWSER_BACK, the block's first key
        (0xB3, False),  # VK_MEDIA_PLAY_PAUSE, what the glasses send when taken off
        (0xB7, False),  # VK_LAUNCH_APP2, the block's last key
    ],
)
def test_only_typed_keys_and_the_mouse_are_real(vk_code: int | None, is_real: bool) -> None:
    assert is_real_input(vk_code) is is_real


@pytest.mark.parametrize("vk_code", [None, 0x41])  # a click, the A key
def test_hooks_wake_on_real_input_after_the_grace_only(vk_code: int | None) -> None:
    clock = [0.0]
    watch = InputWatch(
        5.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: 100,
        clock=lambda: clock[0],
        key_down=NOTHING_DOWN,
    )
    hooks = FakeHooks.installed[0]
    clock[0] = 3.0
    hooks.on_input(0x0D, False)  # the Enter key that ran `sleepmode sleep`
    assert not watch.has_new_input()
    clock[0] = 6.0
    hooks.on_input(0x0D, True)  # ...released after the grace
    hooks.on_input(0xB3, False)  # the glasses' pause
    hooks.on_input(0xAF, False)  # a headset's volume up
    assert not watch.has_new_input()
    hooks.on_input(vk_code, False)
    assert watch.has_new_input()
    watch.close()
    assert hooks.is_closed


def test_injected_input_never_wakes_even_as_missed_input(caplog) -> None:
    # Regression: another program's SendInput key or click woke sleep mode. The hooks get
    # only on_injected for it, while Windows still moves the last-input tick each time.
    ticks, clock = [100], [10.0]
    watch = InputWatch(
        0.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: ticks[0],
        clock=lambda: clock[0],
        key_down=NOTHING_DOWN,
    )
    hooks = FakeHooks.installed[0]
    with caplog.at_level(logging.INFO):
        for step in range(40):  # an injected key or click every 0.25 s for 10 s
            hooks.on_injected()
            ticks[0], clock[0] = 101 + step, 10.0 + step / 4
            assert not watch.has_new_input()
            assert not watch.has_new_input()  # one pump later: still no miss
    assert len(FakeHooks.installed) == 1  # never taken for a miss, so never reinstalled
    assert sum("injected" in r.message for r in caplog.records) == 1  # once a minute
    hooks.on_input(0x41, False)  # the owner's own A key
    assert watch.has_new_input()


def test_a_key_stuck_down_since_before_the_grace_never_wakes() -> None:
    # Regression: Scroll Lock (0x91) stuck down auto-repeated ~30 times a second with no
    # release, and the first repeat after the grace woke sleep mode with nobody there.
    clock, down = [0.0], {0x91}
    watch = InputWatch(
        5.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: 100,
        clock=lambda: clock[0],
        key_down=down.__contains__,
    )
    hooks = FakeHooks.installed[0]
    for step in range(300):  # 0 to ~10 s, a down every 33 ms
        clock[0] = step / 30
        hooks.on_input(0x91, False)
    assert not watch.has_new_input()
    hooks.on_input(0x91, True)  # someone finally lets go...
    assert not watch.has_new_input()
    hooks.on_input(0x91, False)  # ...and a fresh press after that is real
    assert watch.has_new_input()


def test_a_release_the_hooks_missed_doesnt_mute_the_key() -> None:
    # Regression: Enter let go over a UAC prompt stayed "held", so no press of it woke.
    clock, down = [0.0], {0x0D}
    watch = InputWatch(
        5.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: 100,
        clock=lambda: clock[0],
        key_down=down.__contains__,
    )
    hooks = FakeHooks.installed[0]
    clock[0] = 3.0
    hooks.on_input(0x0D, False)  # the Enter that ran `sleepmode sleep`...
    clock[0] = 6.0
    down.clear()  # ...let go where the hooks can't see
    assert not watch.has_new_input()
    hooks.on_input(0x0D, False)
    assert watch.has_new_input()


@pytest.mark.parametrize(
    ("stuck", "also_down"),
    [(0x91, set()), (0xA2, {0x11})],  # Scroll Lock; left Ctrl, whose generic VK_CONTROL is down
)
def test_a_stuck_key_doesnt_wake_when_the_hooks_go_blind(stuck: int, also_down: set) -> None:
    # Regression: the stuck key's auto-repeat moved the tick with no hook call (an
    # elevated window had the focus), and 3 counted misses woke sleep mode.
    ticks, clock = [100], [0.0]
    watch = InputWatch(
        5.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: ticks[0],
        clock=lambda: clock[0],
        key_down=(down := {stuck} | also_down).__contains__,
    )
    hooks = FakeHooks.installed[0]
    for step in range(300):  # the hooks see it repeat until 10 s...
        clock[0], ticks[0] = step / 30, 100 + step
        hooks.on_input(stuck, False)
        assert not watch.has_new_input()
    for step in range(40):  # ...then see nothing for 10 s while the tick keeps moving
        clock[0], ticks[0] = 10.0 + step / 4, 400 + step
        assert not watch.has_new_input()
    # The owner's own clicking the blind hooks miss still wakes it.
    down.add(0x01)
    woke = []
    for step in range(16):
        clock[0], ticks[0] = 20.0 + step / 4, 440 + step
        woke.append(watch.has_new_input())
    assert woke[-1]


# (seconds, x, y) moves after the grace; the default settings want a 100 px span in 1.5 s.
JITTER = [(t * 0.4, 500 + t % 3, 300 - t % 2) for t in range(50)]  # 1-2 px twitches for 20 s
DRIFT = [(t * 1.0, 500 + 5 * t, 300) for t in range(30)]  # 145 px, but only 5 px a second
FLICK = [(0.1 * t, 500 + 30 * t, 300) for t in range(5)]  # 120 px across in 0.4 s
SHAKE = [(0.1 * t, 500 + (60 if t % 2 else -60), 300) for t in range(4)]  # back and forth


@pytest.mark.parametrize(
    ("moves", "should_wake"),
    [(JITTER, False), (DRIFT, False), (FLICK, True), (SHAKE, True)],
)
def test_only_a_deliberate_mouse_move_wakes(moves: list, should_wake: bool) -> None:
    clock = [0.0]
    watch = InputWatch(
        5.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: 100,
        clock=lambda: clock[0],
        key_down=NOTHING_DOWN,
    )
    hooks = FakeHooks.installed[0]
    clock[0] = 1.0
    hooks.on_mouse_move(0, 0)  # during the grace: never part of a span
    for at, x, y in moves:
        clock[0] = 10.0 + at
        hooks.on_mouse_move(x, y)
    assert watch.has_new_input() is should_wake


def test_without_hooks_any_input_after_the_grace_wakes(caplog) -> None:
    def broken_hooks(on_input, on_mouse_move, on_injected) -> None:
        raise OSError("SetWindowsHookExW failed")

    ticks, clock = [100], [0.0]
    with caplog.at_level(logging.WARNING):
        watch = InputWatch(
            5.0,
            InputSettings(),
            broken_hooks,
            read_tick=lambda: ticks[0],
            clock=lambda: clock[0],
            key_down=NOTHING_DOWN,
        )
        ticks[0], clock[0] = 200, 3.0  # the Enter key that ran `sleepmode sleep`
        assert not watch.has_new_input()
        clock[0] = 6.0
        assert not watch.has_new_input()
        ticks[0] = 201  # any input, a media key too: never waking would be worse
        assert watch.has_new_input()
    assert len(caplog.records) == 1  # logged once, not every poll


def test_without_hooks_a_stuck_key_only_lets_other_keys_or_buttons_wake() -> None:
    def broken_hooks(on_input, on_mouse_move, on_injected) -> None:
        raise OSError("SetWindowsHookExW failed")

    ticks, clock, down = [100], [0.0], {0x91}
    watch = InputWatch(
        5.0,
        InputSettings(),
        broken_hooks,
        read_tick=lambda: ticks[0],
        clock=lambda: clock[0],
        key_down=down.__contains__,
    )
    clock[0] = 6.0
    assert not watch.has_new_input()  # the grace has ended with Scroll Lock down
    ticks[0] = 150  # its auto-repeat
    assert not watch.has_new_input()
    down.add(0x01)  # a left click
    ticks[0] = 160
    assert watch.has_new_input()


def test_input_the_hooks_missed_reinstalls_them_then_wakes() -> None:
    ticks, clock = [100], [10.0]
    watch = InputWatch(
        0.0,
        InputSettings(),
        FakeHooks,
        read_tick=lambda: ticks[0],
        clock=lambda: clock[0],
        key_down=NOTHING_DOWN,
    )

    def poll(tick: int, at: float) -> bool:
        ticks[0], clock[0] = tick, at
        return watch.has_new_input()

    first = FakeHooks.installed[0]
    first.on_input(0xB3, False)  # seen by the hooks, and Windows moves the tick a moment later
    assert not poll(100, 10.0) and not poll(101, 10.0)
    assert not poll(102, 10.0)  # no hook call yet...
    first.on_input(0xB3, False)  # ...but it lands within one more pump, so it's no miss
    assert not poll(102, 10.0) and len(FakeHooks.installed) == 1
    # A hook Windows dropped: still no call a poll later is a miss, which reinstalls them.
    assert not poll(103, 10.0) and not poll(103, 10.0)
    assert first.is_closed and len(FakeHooks.installed) == 2
    # The mouse moving over a window the hooks can't see moves the tick every poll. The
    # 10.0 miss has expired by then, and misses under 1 s after a counted one count as it,
    # so the counted misses at 16.25 and 17.25 don't wake, and the one at 18.25 does.
    times = [16.0 + 0.25 * step for step in range(20)]
    woke_at = next((at for tick, at in enumerate(times, start=200) if poll(tick, at)), None)
    assert woke_at == 18.25  # 2.25 s after the mouse started

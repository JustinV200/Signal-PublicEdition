"""InputWatch: notices real keyboard or mouse use since sleep mode started.

Real use is a fresh press of any key but the media, volume, browser and launch keys
(a held key's auto-repeat and every release don't count), any mouse button
or wheel, or a deliberate mouse move (sleepmode.keeper.mouse_travel: an optical mouse's
jitter doesn't count), as the low-level hooks see them (sleepmode.keeper.input_hooks).
Input another program sent (flagged injected) never wakes it, and counts as a hook call,
so the tick move it causes is no miss either (see below).
Bluetooth glasses and headsets send those keys by themselves (taking the glasses off
sends a pause), so they mustn't wake the screens. A key stuck down since before sleep
started (Scroll Lock once auto-repeated ~30 times a second all night, with no release)
only ever repeats, so it can't wake them either; a fresh press of it after a release
can. Each poll checks the held keys with GetAsyncKeyState: one that's up again had a
release the hooks missed (let go over an elevated window, say), so its next press is
fresh, while one still down keeps its repeats from counting as misses. A button that
arrives another way, as a HID consumer-control report or a WM_APPCOMMAND, never
reaches the hooks, so one press can't wake them either.

Fail-safe, both ways rather than never waking:
- if the hooks can't be installed, it falls back to GetLastInputInfo, which counts any
  input at all (media keys too), except while a key that was down when the grace
  ended is still down: then only another key or a mouse button down at the poll counts;
- input the hooks keep missing (GetLastInputInfo moves, no hook call) wakes it too,
  after 3 separate presses in 5 s: see MISSES_TO_WAKE. While a held key is still down,
  a miss counts only if another key or a mouse button is down at the poll.
Input during the grace period after sleep starts is ignored either way.
"""

import ctypes
import functools
import logging
import time
from collections.abc import Callable, Iterable
from ctypes import wintypes

from sleepmode.config import InputSettings
from sleepmode.keeper.input_hooks import InputHooks, OnInjected, OnInput, OnMouseMove
from sleepmode.keeper.mouse_travel import MouseTravel

log = logging.getLogger(__name__)

# VK_BROWSER_BACK (0xA6) up to VK_LAUNCH_APP2 (0xB7) are one block in winuser.h: the
# VK_BROWSER_*, VK_VOLUME_*, VK_MEDIA_* and VK_LAUNCH_* keys, in that order.
FIRST_IGNORED_VK = 0xA6
LAST_IGNORED_VK = 0xB7
ALL_VKS = range(1, 256)
_KEY_DOWN_BIT = 0x8000
# The hooks report a modifier by side, but GetAsyncKeyState also has its generic code
# (VK_SHIFT 0x10, VK_CONTROL 0x11, VK_MENU 0x12) down while either side is held.
GENERIC_MODIFIER = {0xA0: 0x10, 0xA1: 0x10, 0xA2: 0x11, 0xA3: 0x11, 0xA4: 0x12, 0xA5: 0x12}

# A "miss" is input the hooks didn't see: the last-input tick moved and no hook call came,
# even one poll later (Windows may move the tick just before the call lands). Each miss
# reinstalls the hooks, since Windows silently removes one that runs too slow, so after
# a dropped hook the first key (or its own release) only reinstalls it and the next key
# wakes. Misses under MISS_MERGE_S after the last counted one count as that one, so a
# press whose down and up land in two polls counts once. MISSES_TO_WAKE counted misses
# within MISS_WINDOW_S count as real input: the hooks can't see the owner at all then (an
# elevated window has the focus, or the lock screen is up). That takes 3 separate presses
# in 5 s, or about 2.5 s of typing or mouse movement. A button the hooks see is no miss.
MISSES_TO_WAKE = 3
MISS_WINDOW_S = 5.0
MISS_MERGE_S = 1.0
# Ignored mouse jitter and injected input are each logged at most this often, so a
# twitchy mouse or a program sending input can't flood the log.
JITTER_LOG_EVERY_S = 60.0

InstallHooks = Callable[[OnInput, OnMouseMove, OnInjected], InputHooks]


def is_real_input(vk_code: int | None) -> bool:
    """Whether one input event means someone is using the keyboard or mouse.

    Args:
        vk_code: The key's virtual-key code, or None for a mouse button or the wheel.

    Returns:
        False for a media, volume, browser or launch key; True for any other key and
        for every mouse button and the wheel.
    """
    return vk_code is None or not FIRST_IGNORED_VK <= vk_code <= LAST_IGNORED_VK


@functools.cache
def _user32() -> ctypes.WinDLL:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    return user32


def is_key_down(vk_code: int) -> bool:
    """True if the key (or mouse button) is physically down now (GetAsyncKeyState)."""
    return bool(_user32().GetAsyncKeyState(vk_code) & _KEY_DOWN_BIT)


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def last_input_tick() -> int:
    """The tick count (ms since boot, wrapping) of the session's last input of any kind.

    Raises:
        OSError: GetLastInputInfo failed.
    """
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info.dwTime


class InputWatch:
    """Says whether there's been real input since the grace period ended."""

    def __init__(
        self,
        grace_s: float,
        mouse: InputSettings,
        install_hooks: InstallHooks = InputHooks,
        read_tick: Callable[[], int] = last_input_tick,
        clock: Callable[[], float] = time.monotonic,
        key_down: Callable[[int], bool] = is_key_down,
    ) -> None:
        """Start watching now, on the calling thread (which must pump messages).

        Args:
            grace_s: Seconds from now during which input is ignored.
            mouse: How far the mouse must move to count (sleepmode.toml's [input]).
            install_hooks: Installs the hooks with a callback; tests pass a fake.
            read_tick: Reads the last-input tick; tests pass a fake.
            clock: Monotonic seconds; tests pass a fake.
            key_down: Whether a key is physically down now; tests pass a fake.
        """
        self._install_hooks = install_hooks
        self._read_tick = read_tick
        self._clock = clock
        self._key_down = key_down
        self._stuck_vks: set[int] | None = None  # no hooks: keys down when the grace ended
        self._armed_at = clock() + grace_s
        self._baseline = read_tick()
        self._hook_events = 0  # since the last-input tick last moved
        self._ignored_vks: set[int] = set()  # since the last has_new_input
        self._held_vks: set[int] = set()  # keys down with no release seen yet
        self._travel = MouseTravel(mouse)
        self._jitter_moves = 0  # ignored small moves since the last jitter log
        self._next_jitter_log = 0.0
        self._injected_events = 0  # ignored injected events since the last such log
        self._next_injected_log = 0.0
        self._miss_times: list[float] = []  # counted misses within MISS_WINDOW_S
        self._is_suspect = False  # the last poll's tick move had no hook call (yet)
        self._woken_by = ""
        self._hooks = self._try_hooks()

    def has_new_input(self) -> bool:
        """True once real input arrives after the grace period (call after pumping messages)."""
        tick = self._read_tick()
        if self._clock() < self._armed_at:
            # Still in the grace period: input now moves the baseline instead.
            self._baseline, self._hook_events = tick, 0
            return False
        if self._hooks is None:
            return self._ticks_say_input(tick)
        self._check_hooks(tick)
        if self._woken_by:
            log.info("real input: %s", self._woken_by)
        return bool(self._woken_by)

    def close(self) -> None:
        """Remove the hooks. Safe to call twice."""
        if self._hooks is not None:
            self._hooks.close()

    def _on_input(self, vk_code: int | None, is_key_up: bool) -> None:
        """The hooks' callback; it runs inside the hook, so it only takes notes."""
        self._hook_events += 1
        if vk_code is not None:
            # Low-level hooks don't flag auto-repeat, so a down for a key already down
            # is one; neither it nor a release is someone starting to type.
            was_held = vk_code in self._held_vks
            if is_key_up:
                self._held_vks.discard(vk_code)
            else:
                self._held_vks.add(vk_code)
            if is_key_up or was_held:
                return
        if self._clock() < self._armed_at:
            return
        if not is_real_input(vk_code):
            self._ignored_vks.add(vk_code)
        elif not self._woken_by:
            self._woken_by = (
                "a mouse click or the wheel" if vk_code is None else f"key {_hex([vk_code])}"
            )

    def _on_mouse_move(self, x: int, y: int) -> None:
        """The hooks' move callback: wake only on a deliberate move, not jitter."""
        self._hook_events += 1
        now = self._clock()
        if now < self._armed_at or self._woken_by:
            return
        if self._travel.is_deliberate(now, x, y):
            self._woken_by = "the mouse moving"
        else:
            self._jitter_moves += 1

    def _on_injected(self) -> None:
        """The hooks' callback for input another program sent: never wakes.

        It counts as a hook call: it moves the tick too, which would else look like a miss.
        """
        self._hook_events += 1
        if self._clock() >= self._armed_at:
            self._injected_events += 1

    def _log_ignored(self) -> None:
        """Log the media keys, jitter and injected input that didn't wake sleep mode."""
        if self._ignored_vks:
            log.info("not waking for media key(s) %s", _hex(self._ignored_vks))
            self._ignored_vks.clear()
        now = self._clock()
        if self._jitter_moves and now >= self._next_jitter_log:
            log.info("not waking for %d small mouse move(s)", self._jitter_moves)
            self._jitter_moves, self._next_jitter_log = 0, now + JITTER_LOG_EVERY_S
        if self._injected_events and now >= self._next_injected_log:
            log.info("not waking for %d injected input(s)", self._injected_events)
            self._injected_events, self._next_injected_log = 0, now + JITTER_LOG_EVERY_S

    def _check_hooks(self, tick: int) -> None:
        """Log ignored input, and handle input that got past the hooks (MISSES_TO_WAKE)."""
        self._log_ignored()
        has_moved = tick != self._baseline
        # A key that's up again had a release the hooks missed, so its next down is fresh.
        self._held_vks = {vk for vk in self._held_vks if self._key_down(vk)}
        # A suspect still without a hook call one pump later is a miss. While a held key is
        # still down its auto-repeat moves the tick when the hooks go blind, so then only
        # another key or a mouse button down now makes it one (as in the no-hooks fallback).
        is_miss = self._is_suspect and not self._hook_events
        held = self._held_vks | {GENERIC_MODIFIER.get(vk, vk) for vk in self._held_vks}
        if is_miss and (not held or self._other_input_down(held)):
            self._handle_miss()
        was_suspect = self._is_suspect
        self._is_suspect = has_moved and not self._hook_events
        # Hook calls count until the tick moves (Windows may move it just after a call),
        # or until they've cleared a suspect.
        if has_moved or was_suspect:
            self._baseline, self._hook_events = tick, 0

    def _ticks_say_input(self, tick: int) -> bool:
        """The no-hooks fallback: any tick move, except a stuck key's auto-repeat."""
        if self._stuck_vks is None:
            self._stuck_vks = {vk for vk in ALL_VKS if self._key_down(vk)}
        # Ticks wrap every ~49 days, so compare for a change, never for "greater".
        if tick == self._baseline:
            return False
        self._stuck_vks = {vk for vk in self._stuck_vks if self._key_down(vk)}
        if not self._stuck_vks:
            return True
        # The tick moves ~30 times a second for the stuck key, so only another key or a
        # mouse button down right now counts (a mouse move alone can't be told apart).
        self._baseline = tick
        return self._other_input_down(self._stuck_vks)

    def _other_input_down(self, excluded: set[int]) -> bool:
        """Whether a key (not a media key) or mouse button other than excluded is down now."""
        return any(self._key_down(vk) for vk in ALL_VKS if vk not in excluded and is_real_input(vk))

    def _handle_miss(self) -> None:
        """Count a miss: MISSES_TO_WAKE of them wake sleep mode, else reinstall the hooks."""
        now = self._clock()
        self._miss_times = [t for t in self._miss_times if now - t < MISS_WINDOW_S]
        # Measured from the last counted miss, not chained, so steady input still adds up.
        if not self._miss_times or now - self._miss_times[-1] >= MISS_MERGE_S:
            self._miss_times.append(now)
        log.info("input the hooks didn't see (%d in %g s)", len(self._miss_times), MISS_WINDOW_S)
        if len(self._miss_times) >= MISSES_TO_WAKE:
            self._woken_by = f"{len(self._miss_times)} inputs the hooks didn't see"
            return
        log.info("reinstalling the hooks")
        old_hooks, self._hooks = self._hooks, self._try_hooks()
        old_hooks.close()

    def _try_hooks(self) -> InputHooks | None:
        """The installed hooks, or None (logged, and never retried) to fall back to ticks."""
        try:
            return self._install_hooks(self._on_input, self._on_mouse_move, self._on_injected)
        except OSError as error:
            log.warning(
                "couldn't hook the keyboard and mouse (%s); any input now wakes sleep mode, "
                "media keys and injected input included",
                error,
            )
            return None


def _hex(vk_codes: Iterable[int]) -> str:
    return ", ".join(f"0x{vk:02x}" for vk in sorted(vk_codes))

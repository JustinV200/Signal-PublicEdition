"""Plain-text summaries of sleep mode's state, shared by the CLI and the MCP tools."""

from datetime import datetime

from sleepmode.control.machine import SleepStatus
from sleepmode.control.state import SleepState
from sleepmode.screens import BLACK_WINDOW, DDC_OFF, NIGHT_SKY, MonitorResult

_METHOD_TEXT = {
    DDC_OFF: "powered off over DDC/CI",
    BLACK_WINDOW: "black window",
    NIGHT_SKY: "night sky",
}
_TIME_FORMAT = "%H:%M %a %d %b"
WAKE_HINT = "say good morning, run `sleepmode wake`, or touch the mouse or keyboard"


def describe_sleep(state: SleepState) -> str:
    """Summarise a sleep that just started (or the current one)."""
    if state.wake_at is not None:
        head = f"Sleep mode is on until {_when(state.wake_at)}. The PC stays awake."
    else:
        head = f"Sleep mode is on with no wake time ({WAKE_HINT}). The PC stays awake."
    lighting = [f"- {line}" for line in state.lighting]
    return "\n".join([head, *_monitor_lines(state.monitors), *lighting, *_note_lines(state.notes)])


def describe_wake(state: SleepState) -> str:
    """Summarise a wake that just ran."""
    head = "Sleep mode is off; the screens are back."
    if state.notes:
        head = "Sleep mode is off, but not everything came back:"
    return "\n".join([head, *_note_lines(state.notes)])


def describe_status(status: SleepStatus) -> str:
    """Summarise status(): on or off, the wake time, each display, and keeper health."""
    state = status.state
    if state is None:
        return "Sleep mode is off (it hasn't been used yet)."
    if not state.is_asleep:
        woke = f" since {_when(state.woke_at)}" if state.woke_at else ""
        by = f", woken by {state.woke_by}" if state.woke_by else ""
        return "\n".join([f"Sleep mode is off{woke}{by}.", *_note_lines(state.notes)])
    lines = [describe_sleep(state)]
    if not status.is_keeper_running:
        lines.append(
            "Warning: the keeper process isn't running, so the PC isn't held awake and input "
            "won't wake the screens. Run `sleepmode wake`, then sleep again if you like."
        )
    return "\n".join(lines)


def _monitor_lines(monitors: tuple[MonitorResult, ...]) -> list[str]:
    lines = []
    for monitor in monitors:
        role = ", projector" if monitor.is_projector else ""
        detail = f" ({monitor.detail})" if monitor.detail else ""
        lines.append(f"- {monitor.label}{role}: {_METHOD_TEXT[monitor.method]}{detail}")
    return lines


def _note_lines(notes: tuple[str, ...]) -> list[str]:
    return [f"Note: {note}" for note in notes]


def _when(moment: datetime) -> str:
    return moment.strftime(_TIME_FORMAT)

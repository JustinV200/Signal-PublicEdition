"""OpenRgbBackend: every device OpenRGB's SDK server lists goes dark at sleep, back at wake.

Sleep puts each device in its "Off" mode, or Direct mode with every LED black. Wake
loads the `day` profile, else the `sleepmode-before` snapshot. Only with no `day`
profile does sleep save that snapshot first (wake would never use it otherwise), and
not when this sleep replaces one that already darkened the lights, or when they
already look off. Nothing is ever saved to a device's own memory, and USB power is
never touched (the keyboard and mouse wake sleep mode). Each session is registered
with the step's StepGuard, so an abandoned step's socket is closed, and sleep stops
before its next device once the guard is abandoned.
"""

import logging
from collections.abc import Callable

from openrgb import OpenRGBClient
from openrgb.orgb import Device
from openrgb.utils import ModeColors

from sleepmode.config import DAY_PROFILE, SNAPSHOT_PROFILE
from sleepmode.lighting.backend import LightingReport
from sleepmode.lighting.openrgb_server import OpenRgbSession
from sleepmode.lighting.step_guard import StepGuard

log = logging.getLogger(__name__)

# The mode name OpenRGB gives a device's own lights-off effect (matched case-insensitively).
OFF_MODE_NAME = "off"
NO_DAY_NOTE = (
    f"OpenRGB has no `{DAY_PROFILE}` profile, so wake will load the `{SNAPSHOT_PROFILE}` "
    "snapshot, which can't bring back lights OpenRGB never set. Save the daytime look in "
    f"OpenRGB as `{DAY_PROFILE}`."
)
NOTHING_TO_LOAD_NOTE = (
    f"OpenRGB has neither a `{DAY_PROFILE}` nor a `{SNAPSHOT_PROFILE}` profile, so the lights "
    f"stay as they are. Set them in OpenRGB and save the look as `{DAY_PROFILE}`."
)

OpenSession = Callable[[], OpenRgbSession | None]


class OpenRgbBackend:
    """The OpenRGB backend (see the module doc)."""

    name = "OpenRGB"

    def __init__(self, open_session: OpenSession) -> None:
        """Args: open_session connects (starting the server if needed), or answers None
        when OpenRGB isn't there; openrgb_server.open_openrgb in real use."""
        self._open_session = open_session

    def off(self, may_snapshot: bool, guard: StepGuard) -> LightingReport:
        """Snapshot the look if there's no `day` profile (and it's allowed and needed),
        then turn every device off, stopping once guard is abandoned.

        Raises:
            OSError: The server couldn't be reached or started, or a needed snapshot
                couldn't be saved (then no light is turned off, so none is left dark
                without a way back).
        """
        session = self._open_session()
        if session is None:
            return LightingReport()
        guard.close_on_abandon(session.close)
        try:
            return _turn_all_off(session, may_snapshot, guard)
        finally:
            session.close()

    def restore(self, guard: StepGuard) -> LightingReport:
        """Load the `day` profile, else the snapshot.

        Raises:
            OSError: The server couldn't be reached or started.
        """
        session = self._open_session()
        if session is None:
            return LightingReport()
        guard.close_on_abandon(session.close)
        try:
            return _load_daytime_look(session.client)
        finally:
            session.close()


def _turn_all_off(session: OpenRgbSession, may_snapshot: bool, guard: StepGuard) -> LightingReport:
    if not session.client.devices:
        log.info("lighting: OpenRGB lists no devices; skipping")
        return LightingReport()
    notes: list[str] = []
    has_snapshot = False
    if not _has_profile(session.client, DAY_PROFILE):
        notes.append(NO_DAY_NOTE)
        has_snapshot = _save_snapshot(session, may_snapshot)
    # After a snapshot this is a fresh connection (OpenRgbSession.save_profile).
    devices = session.client.devices
    turned_off = _turn_off_each(devices, notes, guard)
    line = f"OpenRGB turned off {turned_off} of {len(devices)} devices"
    if has_snapshot:
        line += f", after saving their look as `{SNAPSHOT_PROFILE}`"
    if session.started_server:
        line += "; sleepmode started OpenRGB's server, which stays running"
    return LightingReport((line,), tuple(notes))


def _save_snapshot(session: OpenRgbSession, may_snapshot: bool) -> bool:
    """Save the current look as SNAPSHOT_PROFILE unless that would lose the real one.

    Raises:
        OSError: It couldn't be saved; the lights then stay on rather than go dark
            with no way back.
    """
    if not may_snapshot:
        log.info("lighting: this sleep replaces one that turned the lights off; no new snapshot")
        return False
    if all(_is_dark(device) for device in session.client.devices):
        # Off already, or OpenRGB just started and hasn't set them: it reports Direct
        # black for devices it can't read back, and a snapshot of that restores nothing.
        log.info("lighting: OpenRGB's lights already look off; no snapshot")
        return False
    session.save_profile(SNAPSHOT_PROFILE)
    return True


def _turn_off_each(devices: list[Device], notes: list[str], guard: StepGuard) -> int:
    """Darken each device in turn; returns how many went off."""
    turned_off = 0
    for device in devices:
        if guard.is_abandoned:
            # Lighting gave up on this step, and a later wake may already have restored
            # the lights: going on would leave them dark all day.
            log.warning("lighting: OpenRGB's off step was abandoned; leaving the rest alone")
            break
        turned_off += _turn_off(device, notes)
    return turned_off


def _turn_off(device: Device, notes: list[str]) -> bool:
    """Darken one device; a failure is logged and noted so the others still go off."""
    try:
        off_mode = next((m for m in device.modes if m.name.lower() == OFF_MODE_NAME), None)
        if off_mode is not None:
            device.set_mode(off_mode)  # never save=True: that writes the device's memory
        else:
            device.off()  # Direct (custom) mode, every LED black
    except Exception as error:  # openrgb-python raises assorted types for one bad device
        log.warning("lighting: OpenRGB couldn't turn off %s: %s", device.name, error)
        notes.append(f"OpenRGB couldn't turn off {device.name}: {error}")
        return False
    log.info("lighting: OpenRGB turned off %s", device.name)
    return True


def _load_daytime_look(client: OpenRGBClient) -> LightingReport:
    profile = next((p for p in (DAY_PROFILE, SNAPSHOT_PROFILE) if _has_profile(client, p)), None)
    if profile is None:
        log.warning("lighting: OpenRGB has no %s or %s profile", DAY_PROFILE, SNAPSHOT_PROFILE)
        return LightingReport(notes=(NOTHING_TO_LOAD_NOTE,))
    client.load_profile(profile)
    log.info("lighting: OpenRGB loaded the %s profile", profile)
    return LightingReport((f"OpenRGB loaded the `{profile}` profile",))


def _is_dark(device: Device) -> bool:
    """In its Off mode, or in a per-LED mode with every LED black."""
    mode = device.modes[device.active_mode]
    if mode.name.lower() == OFF_MODE_NAME:
        return True
    is_black = not any(color.red or color.green or color.blue for color in device.colors)
    return mode.color_mode == ModeColors.PER_LED and is_black


def _has_profile(client: OpenRGBClient, name: str) -> bool:
    """Whether the server lists the profile (openrgb-python matches names case-insensitively)."""
    return any(profile.name.lower() == name.lower() for profile in client.profiles)

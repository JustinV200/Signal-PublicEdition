"""Lighting: sleep's lights-off and wake's restore, across every backend, never raising.

The backends run in order: OpenRGB (most brands), Windows Dynamic Lighting (a stub
for now), then the owner's vendor commands from sleepmode.toml. Each finds its own
devices at run time and logs at INFO when it has nothing to do. Each gets
LIGHTING_STEP_TIMEOUT_S in all, and any error or overrun becomes a note, so lighting
can never hold up or break a sleep or a wake. A backend that overruns is abandoned
through its StepGuard (step_guard.py), so it can't change a light after that.

A sleepmode.toml that can't be read is a note too. Sleep then leaves the lights
alone, while wake brings them back with the default settings.
"""

import logging
from collections.abc import Callable
from functools import partial
from pathlib import Path

from sleepmode.config import (
    LIGHTING_STEP_TIMEOUT_S,
    ConfigError,
    LightingSettings,
    load_lighting_settings,
)
from sleepmode.lighting.backend import Backend, LightingReport
from sleepmode.lighting.commands import CommandBackend, RunCommand, run_command
from sleepmode.lighting.deadline import run_with_deadline
from sleepmode.lighting.lamparray import LampArrayBackend
from sleepmode.lighting.openrgb_backend import OpenRgbBackend
from sleepmode.lighting.openrgb_server import OpenRgbSession, open_openrgb, resolve_openrgb_path
from sleepmode.lighting.step_guard import StepGuard

log = logging.getLogger(__name__)

# open_openrgb(exe_path): connect or start; None when OpenRGB isn't there.
OpenOpenRgb = Callable[[Path | None], OpenRgbSession | None]
# One backend's off or restore, given the step's guard.
StepCall = Callable[[Backend, StepGuard], LightingReport]
_STEP_TEXT = {"off": "turn the lights off", "restore": "bring the lights back"}


class Lighting:
    """Turns every light it can reach off at sleep and back on at wake."""

    def __init__(
        self,
        config_path: Path,
        open_session: OpenOpenRgb = open_openrgb,
        run: RunCommand = run_command,
        step_timeout_s: float = LIGHTING_STEP_TIMEOUT_S,
    ) -> None:
        """Args:
        config_path: sleepmode.toml, read on every call so an edit applies at once.
        open_session: Connects to OpenRGB (fakes in tests).
        run: Runs one vendor command (fakes in tests).
        step_timeout_s: Each backend's deadline for one off or restore.
        """
        self._config_path = config_path
        self._open_session = open_session
        self._run = run
        self._step_timeout_s = step_timeout_s

    def off(self, may_snapshot: bool) -> LightingReport:
        """Turn the lights off. Never raises: failures are notes.

        Args:
            may_snapshot: False when this sleep replaces one that already darkened
                the lights, so the saved "before" look isn't overwritten.
        """
        return self._run_step("off", lambda backend, guard: backend.off(may_snapshot, guard))

    def restore(self) -> LightingReport:
        """Bring the lights back to their daytime look. Never raises: failures are notes."""
        return self._run_step("restore", lambda backend, guard: backend.restore(guard))

    def _run_step(self, step: str, call: StepCall) -> LightingReport:
        settings, report = self._settings_for(step)
        backends = self._backends(settings) if settings is not None else []
        for backend in backends:
            report = report.plus(self._run_backend(backend, step, call))
        return report

    def _settings_for(self, step: str) -> tuple[LightingSettings | None, LightingReport]:
        """sleepmode.toml's settings, or, when it can't be read, a fallback and a note.

        Returns:
            The settings (None: leave the lights alone) and the report to start from.
        """
        try:
            return load_lighting_settings(self._config_path), LightingReport()
        except ConfigError as error:
            if step == "off":
                # A broken file could mean "leave them alone", so sleep doesn't guess.
                log.warning("lighting: %s; leaving the lights alone", error)
                return None, LightingReport(notes=(f"The lights were left alone: {error}",))
            # The lights may be dark from the night, and dark all day is the worse mistake,
            # so wake uses the defaults: OpenRGB at its default path, loading `day`.
            log.warning("lighting: %s; bringing the lights back with the defaults", error)
            note = f"The lights were brought back with the default settings: {error}"
            return LightingSettings(), LightingReport(notes=(note,))

    def _run_backend(self, backend: Backend, step: str, call: StepCall) -> LightingReport:
        """One backend's step under the deadline; any failure becomes a note.

        An overrun abandons the step's guard, which closes its connection and stops it
        before its next change, so it can't undo a later step (say, wake's restore).
        """
        label = f"{backend.name} {step}"
        guard = StepGuard()
        try:
            return run_with_deadline(
                lambda: call(backend, guard), self._step_timeout_s, label, on_timeout=guard.abandon
            )
        except Exception as error:  # third-party backends raise anything; sleep must go on
            log.warning("lighting: %s failed: %s", label, error, exc_info=True)
            return LightingReport(notes=(f"{backend.name} couldn't {_STEP_TEXT[step]}: {error}",))

    def _backends(self, settings: LightingSettings) -> list[Backend]:
        """The backends in order; none when lighting is disabled."""
        if not settings.enabled:
            log.info("lighting: disabled in sleepmode.toml; leaving the lights alone")
            return []
        exe_path = resolve_openrgb_path(settings.openrgb_path)
        return [
            OpenRgbBackend(partial(self._open_session, exe_path)),
            LampArrayBackend(),
            CommandBackend(settings.off_commands, settings.restore_commands, self._run),
        ]

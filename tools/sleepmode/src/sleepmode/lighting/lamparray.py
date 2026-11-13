"""LampArrayBackend: Windows Dynamic Lighting (HID LampArray). A stub that finds no devices.

No device it has been tried with speaks LampArray, so this only
holds the backend's place in the order: after OpenRGB, before vendor commands.
"""

import logging

from sleepmode.lighting.backend import LightingReport
from sleepmode.lighting.step_guard import StepGuard

log = logging.getLogger(__name__)


class LampArrayBackend:
    """Dynamic Lighting devices: none, until it's built (see the TODO)."""

    # TODO: build this when a LampArray device turns up. Find devices with
    # LampArray.GetDeviceSelector() and DeviceInformation.FindAllAsync (pywinrt
    # winrt-Windows.Devices.Lights and winrt-Windows.Devices.Enumeration), open each
    # with LampArray.FromIdAsync, set black (or BrightnessLevel = 0) at sleep and
    # release it at wake. The catch: an unpackaged process only controls lamps while
    # it's the foreground app, and sleepmode never is. Background control needs package
    # identity (MSIX, or a sparse package declaring the com.microsoft.windows.lighting
    # AppExtension) and the owner ranking it under Settings > Personalization > Dynamic
    # Lighting > Background light control. Skip devices OpenRGB already turned off.

    name = "Dynamic Lighting"

    def off(self, may_snapshot: bool, guard: StepGuard) -> LightingReport:
        """Report no LampArray devices (may_snapshot and guard don't apply)."""
        return self._skip()

    def restore(self, guard: StepGuard) -> LightingReport:
        """Report no LampArray devices (guard doesn't apply)."""
        return self._skip()

    def _skip(self) -> LightingReport:
        log.info("lighting: Dynamic Lighting: no LampArray devices (not built yet); skipping")
        return LightingReport()

"""Public API of sleepmode.lighting: RGB lights off at sleep and back at wake, brand-agnostic."""

from sleepmode.lighting.backend import LightingReport
from sleepmode.lighting.openrgb_server import OpenRgbSession, open_openrgb
from sleepmode.lighting.switch import Lighting, OpenOpenRgb

__all__ = [
    "Lighting",
    "LightingReport",
    "OpenOpenRgb",
    "OpenRgbSession",
    "open_openrgb",
]

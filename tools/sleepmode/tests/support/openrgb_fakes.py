"""A fake OpenRGB SDK server: devices with modes and colours, and a profile list.

It stands in for openrgb-python's OpenRGBClient (the same attributes and calls the
OpenRGB backend uses), and keeps its state between sessions like the real server.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from openrgb.utils import ModeColors, RGBColor

from sleepmode.lighting import OpenOpenRgb, OpenRgbSession

RED = RGBColor(255, 0, 0)
BLACK = RGBColor(0, 0, 0)
LED_COUNT = 3


@dataclass
class FakeMode:
    name: str
    color_mode: ModeColors


@dataclass
class FakeProfile:
    name: str


class FakeDevice:
    """A device lit in a hardware effect, with Direct, Off and Spectrum Cycle modes."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.modes = [
            FakeMode("Direct", ModeColors.PER_LED),
            FakeMode("Off", ModeColors.NONE),
            FakeMode("Spectrum Cycle", ModeColors.NONE),
        ]
        self.light_up()

    def light_up(self) -> None:
        """Back to Spectrum Cycle, as if something relit it."""
        self.active_mode = 2
        self.colors = [RED] * LED_COUNT

    def set_mode(self, mode: FakeMode) -> None:
        self.active_mode = self.modes.index(mode)

    def off(self) -> None:
        self.active_mode = 0
        self.colors = [BLACK] * LED_COUNT

    @property
    def is_dark(self) -> bool:
        return self.modes[self.active_mode].name == "Off"


@dataclass
class FakeOpenRgb:
    """The server, and each connection to it. `saved` and `loaded` record profile saves and
    loads, in order; `disconnects` counts closed connections."""

    devices: list[FakeDevice]
    profiles: list[FakeProfile] = field(default_factory=list)
    saved: list[str] = field(default_factory=list)
    loaded: list[str] = field(default_factory=list)
    disconnects: int = 0

    def save_profile(self, name: str) -> None:
        self.saved.append(name)
        if name not in self.profile_names:
            self.profiles.append(FakeProfile(name))

    def save_with_cli(self, client: "FakeOpenRgb", name: str) -> "FakeOpenRgb":
        """The CLI save: the old connection is closed and a fresh one comes back."""
        client.disconnect()
        self.save_profile(name)
        return self

    def load_profile(self, name: str) -> None:
        self.loaded.append(name)

    def disconnect(self) -> None:
        self.disconnects += 1

    @property
    def profile_names(self) -> list[str]:
        return [profile.name for profile in self.profiles]

    def opener(self, started_server: bool = False) -> OpenOpenRgb:
        """An open_session stand-in that always connects to this server."""
        return lambda exe_path: OpenRgbSession(self, started_server, self.save_with_cli)


def make_server(names: Sequence[str] = ("Keyboard", "Mouse")) -> FakeOpenRgb:
    """A server whose devices are all lit."""
    return FakeOpenRgb([FakeDevice(name) for name in names])

"""Frozen settings dataclasses: one per config section, plus the `Settings` root.

All defaults live here. A TOML file (see loader.py and whiteboard.example.toml)
overrides them key by key. Fields declared with `bounded()` get range-checked on
load, and fields declared with `one_of()` are checked against their allowed values.
"""

from dataclasses import dataclass, field

from whiteboard.config.validation import bounded, one_of

# Values accepted by [camera] backend: OpenCV's Media Foundation or DirectShow
# capture API, or "any" to let OpenCV pick.
CAMERA_BACKENDS: tuple[str, ...] = ("msmf", "dshow", "any")


@dataclass(frozen=True)
class DisplaySettings:
    """The projector, the daemon's HTTP port (on 127.0.0.1 only), and the board page kiosk.

    `name_match` is a case-insensitive substring of the monitor's friendly name
    or its `\\\\.\\DISPLAYn` device name. With no match, the non-primary display is used.
    `fit_height` is the logical stage height once a board fit (keystone quad) is
    set; the width follows the board's aspect ratio.
    """

    name_match: str = "PROJ-1"
    # No host setting: the daemon always binds 127.0.0.1, never a public interface.
    port: int = bounded(8770, minimum=1, maximum=65535)
    launch_kiosk: bool = True
    # Empty means auto-detect msedge.exe in the usual install folders.
    edge_path: str = ""
    fit_height: int = bounded(720, minimum=100, maximum=4320)


@dataclass(frozen=True)
class CameraSettings:
    """Which webcam to open and at what resolution."""

    index: int = bounded(0, minimum=0)
    width: int = bounded(1920, minimum=1)
    height: int = bounded(1080, minimum=1)
    backend: str = one_of("msmf", CAMERA_BACKENDS)


@dataclass(frozen=True)
class CaptureSettings:
    """Clean captures: how long the page stays black, and how many snapshots to keep."""

    blank_ms: int = bounded(250, minimum=0, maximum=5000)
    keep_snapshots: int = bounded(50, minimum=1)


@dataclass(frozen=True)
class WatcherSettings:
    """When a change on the board is worth a clean capture, and waking the agent for.

    `pixel_threshold` is the grey-level difference (0-255) that counts a pixel as
    changed. `motion_ratio` is the changed-pixel fraction between samples that
    means someone is drawing. `ink_change_ratio` is the changed-pixel fraction
    between clean captures that counts as new ink. Captures are `min_interval_s`
    apart unless the live view already shows a large ink change. For `settle_s`
    after the daemon changed the page itself (a blank, the markers, a drawing),
    nothing it sees counts as motion. Under `dark_floor` (the live view's median
    grey, 0-255) the room is too dark to read ink, so no capture is taken.
    """

    enabled: bool = True
    sample_s: float = bounded(1.0, minimum=0.1)
    stable_s: float = bounded(4.0, minimum=0.0)
    min_interval_s: float = bounded(30.0, minimum=0.0)
    pixel_threshold: int = bounded(40, minimum=1, maximum=255)
    motion_ratio: float = bounded(0.01, minimum=0.0, maximum=1.0)
    ink_change_ratio: float = bounded(0.0003, minimum=0.0, maximum=1.0)
    settle_s: float = bounded(3.0, minimum=0.0)
    dark_floor: float = bounded(30.0, minimum=0.0, maximum=255.0)


@dataclass(frozen=True)
class AgentSettings:
    """The board agent: a Claude session that reacts to board changes.

    With `triage` on, a cheap `triage_model` call decides first whether the new
    writing is meant for Claude; `triage_timeout_s` caps that call. The TODO
    view's cross-out check uses the same model and timeout. With
    `verify_after_draw` on, a turn that drew gets one follow-up look at the result.
    A turn still running after `turn_timeout_s` is given up (a hung CLI).
    """

    enabled: bool = True
    model: str = "sonnet"
    triage: bool = True
    triage_model: str = "haiku"
    triage_timeout_s: float = bounded(15.0, minimum=1.0)
    verify_after_draw: bool = True
    # Above the 120 s permission dialog, so a turn waiting on the owner isn't cut short.
    turn_timeout_s: float = bounded(300.0, minimum=130.0)


@dataclass(frozen=True)
class AlignSettings:
    """Automatic re-alignment when the camera, projector or board moves.

    With `auto` on, the board's outline in the camera is compared with the
    current fit after each watcher capture, and every `check_s` seconds while
    the board is idle. Two checks in a row off by more than `drift_px` (mean
    corner error, camera px) re-run calibration and the board fit. Every
    `marker_check_s` while idle the markers are flashed and solved too, which
    catches a projector that moved on its own. Neither timed check runs while the
    room is under [watcher] dark_floor. A new calibration is only kept if
    its reprojection error is at most `max_reprojection_px` (projector px).
    """

    auto: bool = True
    check_s: float = bounded(1800.0, minimum=10.0)
    marker_check_s: float = bounded(3600.0, minimum=60.0)
    drift_px: float = bounded(15.0, minimum=1.0)
    # RANSAC drops corners over 3 px, so a usable limit sits below that.
    max_reprojection_px: float = bounded(2.0, minimum=0.1, maximum=3.0)


@dataclass(frozen=True)
class IdleSettings:
    """The idle view: the board's default when nothing is drawn (whiteboard.daemon.idle).

    With `auto` on, the board switches to it once the items view has had no items
    (the "thinking" box aside) for `empty_s`. Weather is for the PC's place from an IP
    lookup at daemon start and every `locate_hours` when `locate` is on, else (and
    whenever the lookup fails with nothing cached) for `place` at `lat`/`lon`. The
    weather and the headline from `news_feed` (an https RSS 2.0 or Atom feed, labelled
    `news_source`) refresh every `weather_min` and `news_min` minutes; the headlines
    scroll by in the footer at `ticker_px_s` design pixels a second. `tag_labels`
    gives course chips a short name, as "tag=Label"; other tags show title-cased.
    New ink on the physical board blanks the idle view, and the rule then waits until
    no new ink has been seen for `ink_quiet_minutes` (or the ink is wiped off again).
    The board counts as having new ink once at least `ink_min_ratio` of its pixels
    is ink added (small additions add up for a few minutes; erasing never counts).
    """

    auto: bool = True
    empty_s: float = bounded(10.0, minimum=1.0)
    ink_quiet_minutes: float = bounded(10.0, minimum=0.0)
    ink_min_ratio: float = bounded(0.0015, minimum=0.0, maximum=1.0)
    locate: bool = True
    locate_hours: float = bounded(6.0, minimum=1.0, maximum=24.0)
    place: str = "Springfield, IL"
    lat: float = bounded(39.7817, minimum=-90.0, maximum=90.0)
    lon: float = bounded(-89.6501, minimum=-180.0, maximum=180.0)
    news_feed: str = "https://www.allsides.com/rss/news"
    news_source: str = "AllSides"
    weather_min: float = bounded(30.0, minimum=5.0)
    news_min: float = bounded(30.0, minimum=5.0)
    ticker_px_s: float = bounded(75.0, minimum=20.0, maximum=200.0)
    tag_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    """All whiteboard settings. Each attribute is one [section] of the TOML file."""

    display: DisplaySettings = field(default_factory=DisplaySettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    watcher: WatcherSettings = field(default_factory=WatcherSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    align: AlignSettings = field(default_factory=AlignSettings)
    idle: IdleSettings = field(default_factory=IdleSettings)

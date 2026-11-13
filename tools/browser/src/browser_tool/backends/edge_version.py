"""Refuse a browser image whose Edge has fallen behind Microsoft's Linux stable channel.

The image freezes Edge at build time, and a stale browser is the likeliest way
into a container. At each job start the backend compares the image's Edge
(read once per image id) with the newest microsoft-edge-stable in the Edge
repo's Packages.gz (fetched with urllib, cached for a day). A major version
behind refuses the job and names the rebuild command; an older build only
warns in the log. It never compares with the desktop's Edge, which is often the
staler one. If the feed can't be fetched, the job goes ahead with a warning:
the check guards patch lag, and a PC that can't reach Microsoft can't reach
most pages either.
"""

import gzip
import logging
import re
import time
import urllib.request
from collections.abc import Callable

from browser_tool.backends.types import BackendError

logger = logging.getLogger(__name__)

PACKAGES_URL = (
    "https://packages.microsoft.com/repos/edge/dists/stable/main/binary-amd64/Packages.gz"
)
EDGE_PACKAGE = "microsoft-edge-stable"
LATEST_CACHE_S = 24 * 60 * 60
FETCH_TIMEOUT_S = 15.0
# The feed is about 60 KB; anything far bigger isn't it.
MAX_FEED_BYTES = 8 * 1024 * 1024
REBUILD_COMMAND = "docker build --pull --no-cache -t signal-browser:latest tools/browser/docker"
_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\.(\d+)\b")

Version = tuple[int, ...]


def parse_version(text: str) -> Version:
    """The first a.b.c.d version in `text` (e.g. "Microsoft Edge 155.0.4283.62").

    Raises:
        ValueError: If there is none.
    """
    match = _VERSION_RE.search(text)
    if match is None:
        raise ValueError("no Edge version found")
    return tuple(int(part) for part in match.groups())


def latest_stable(packages: str) -> Version:
    """The newest microsoft-edge-stable version listed in an apt Packages file.

    Raises:
        ValueError: If the file lists none.
    """
    versions = []
    for stanza in packages.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in stanza.splitlines() if ": " in line)
        if fields.get("Package") == EDGE_PACKAGE and "Version" in fields:
            versions.append(parse_version(fields["Version"]))
    if not versions:
        raise ValueError(f"no {EDGE_PACKAGE} in the package list")
    return max(versions)


def compare_versions(image: Version, latest: Version) -> str | None:
    """Judge the image's Edge against the latest stable one.

    Returns:
        None when it is current, or a warning when only the build is behind.

    Raises:
        BackendError: When its major version is behind; the message names the rebuild command.
    """
    shown = f"the browser image has Edge {_dotted(image)}, the latest is {_dotted(latest)}"
    if image[0] < latest[0]:
        raise BackendError(f"refused: {shown}. Ask the owner to rebuild it: {REBUILD_COMMAND}")
    if image < latest:
        return f"{shown}; rebuild soon: {REBUILD_COMMAND}"
    return None


def fetch_packages() -> str:
    """Download and unpack the Edge repo's Packages.gz.

    Raises:
        OSError: On a network failure, or a feed that isn't gzip or is too big.
    """
    with urllib.request.urlopen(PACKAGES_URL, timeout=FETCH_TIMEOUT_S) as response:
        packed = response.read(MAX_FEED_BYTES + 1)
    if len(packed) > MAX_FEED_BYTES:
        raise OSError("Packages.gz is larger than expected")
    return gzip.decompress(packed).decode("utf-8", errors="replace")


class EdgeVersionCheck:
    """Caches the image's version per image id and the latest one for a day."""

    def __init__(
        self,
        read_image_version: Callable[[str], str],
        fetch: Callable[[], str] = fetch_packages,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Args:
        read_image_version: Image name -> its `microsoft-edge --version` output.
        fetch: Returns the Packages file text; tests pass a fake.
        clock: Monotonic seconds.
        """
        self._read_image_version = read_image_version
        self._fetch = fetch
        self._clock = clock
        self._image_versions: dict[str, Version] = {}
        self._latest: tuple[Version, float] | None = None

    def ensure_current(self, image: str, image_id: str) -> None:
        """Refuse a stale image; log a warning for a build that is only slightly behind.

        Blocking (docker and HTTP), so callers run it in a worker thread.

        Raises:
            BackendError: If the image's Edge is a major version behind, or unreadable.
        """
        if image_id not in self._image_versions:
            try:
                self._image_versions[image_id] = parse_version(self._read_image_version(image))
            except ValueError:
                raise BackendError(f"couldn't read the Edge version in {image}") from None
        latest = self._latest_version()
        if latest is None:
            return
        warning = compare_versions(self._image_versions[image_id], latest)
        if warning:
            logger.warning(warning)

    def _latest_version(self) -> Version | None:
        now = self._clock()
        if self._latest is not None and now - self._latest[1] < LATEST_CACHE_S:
            return self._latest[0]
        try:
            latest = latest_stable(self._fetch())
        except (OSError, ValueError, EOFError) as error:
            logger.warning("Edge version check skipped: %s", type(error).__name__)
            return None
        self._latest = (latest, now)
        return latest


def _dotted(version: Version) -> str:
    return ".".join(str(part) for part in version)

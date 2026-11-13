"""The image's Edge against the repo's latest stable: a major version behind is refused."""

import pytest

from browser_tool.backends import BackendError
from browser_tool.backends.edge_version import EdgeVersionCheck

# Two stanzas of an apt Packages file; only microsoft-edge-stable counts.
PACKAGES = (
    "Package: microsoft-edge-stable\nVersion: 155.0.4283.62-1\nArchitecture: amd64\n\n"
    "Package: microsoft-edge-dev\nVersion: 157.0.1.2-1\nArchitecture: amd64\n"
)


@pytest.mark.parametrize(
    ("image_version", "is_refused"),
    [
        ("Microsoft Edge 154.0.4200.10 ", True),
        ("Microsoft Edge 155.0.4283.45 ", False),  # only the build is behind: a warning
        ("Microsoft Edge 155.0.4283.62 ", False),
    ],
)
def test_major_behind_image_is_refused(image_version, is_refused):
    check = EdgeVersionCheck(lambda _image: image_version, fetch=lambda: PACKAGES)
    if is_refused:
        with pytest.raises(BackendError):
            check.ensure_current("signal-browser:latest", "sha256:1")
    else:
        check.ensure_current("signal-browser:latest", "sha256:1")

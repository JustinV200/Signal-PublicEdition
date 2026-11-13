"""Layer 1 of the docker jobs' block: the host and private addresses stay refused (allow_all)."""

import pytest

from browser_tool.policy import GuestBlock, HostPolicy

HOST_IP = "203.0.113.65"


@pytest.mark.parametrize(
    ("url", "is_allowed"),
    [
        ("http://host.docker.internal:8770/", False),
        ("http://100.64.0.1/", False),
        ("http://[::ffff:127.0.0.1]:8770/", False),
        (f"http://{HOST_IP}:1234/", False),
        ("http://2130706433/", False),
        ("http://0x7f000001/", False),
        ("http://127.1/", False),
        ("http://0177.0.0.1/", False),
        ("https://example.com/", True),
    ],
)
def test_guest_block_holds_under_allow_all(url, is_allowed):
    policy = HostPolicy.from_strings(
        [], [], is_allow_all=True, guest_block=GuestBlock(lambda: {HOST_IP})
    )
    assert policy.check_url(url).is_allowed is is_allowed

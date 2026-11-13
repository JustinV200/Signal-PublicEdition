"""Security table for browser_tool.visit.login.is_fill_allowed, with the real hosts."""

import pytest

from browser_tool.config import VisitSettings
from browser_tool.visit import login

CAS = "https://sso.example.edu/cas/login"
TARGET = "https://lms.example.edu/mod/assign/index.php?id=1001"
MOODLE_SERVICE = "https%3A%2F%2Flms.example.edu%2Flogin%2Findex.php"
VISIT = VisitSettings(
    login_host="sso.example.edu",
    login_from_hosts=("lms.example.edu",),
    login_credential="school",
)


@pytest.mark.parametrize(
    ("target_url", "page_url", "is_allowed"),
    [
        (TARGET, f"{CAS}?service={MOODLE_SERVICE}", True),
        # A fully qualified (trailing-dot) login host is the same host.
        (TARGET, f"https://sso.example.edu./cas/login?service={MOODLE_SERVICE}", True),
        # The service is on another host, a lookalike, or behind userinfo.
        (TARGET, f"{CAS}?service=https%3A%2F%2Fevil.com%2F", False),
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu.evil.com%2F", False),
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu%40evil.com%2F", False),
        # An explicit port, even the default one or a bare ":".
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu%3A8443%2F", False),
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu%3A443%2F", False),
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu%3A%2F", False),
        (TARGET, f"{CAS}?service=https%3A%2F%2Flms.example.edu%3Ax%2F", False),
        # A plain-http service.
        (TARGET, f"{CAS}?service=http%3A%2F%2Flms.example.edu%2F", False),
        # Two services, blank duplicates included.
        (TARGET, f"{CAS}?service={MOODLE_SERVICE}&service={MOODLE_SERVICE}", False),
        (TARGET, f"{CAS}?service=&service={MOODLE_SERVICE}", False),
        (TARGET, f"{CAS}?service&service={MOODLE_SERVICE}", False),
        # No service at all (a script navigation to CAS).
        (TARGET, CAS, False),
        # The page isn't on the login host.
        (TARGET, f"https://sso.example.edu.evil.com/cas/login?service={MOODLE_SERVICE}", False),
        # The target's host isn't listed.
        ("https://other.example.edu/", f"{CAS}?service={MOODLE_SERVICE}", False),
    ],
    ids=[
        "valid",
        "trailing-dot",
        "other-host",
        "lookalike",
        "userinfo",
        "port",
        "default-port",
        "empty-port",
        "bad-port",
        "http",
        "two-services",
        "blank-duplicate",
        "valueless-duplicate",
        "no-service",
        "page-off-login-host",
        "target-not-listed",
    ],
)
def test_is_fill_allowed(monkeypatch, target_url, page_url, is_allowed):
    # tests/visit/conftest.py relaxes the scheme and port for the http fixtures; not here.
    monkeypatch.setattr(login, "SERVICE_SCHEME", "https")
    monkeypatch.setattr(login, "ALLOW_SERVICE_PORT", False)
    assert login.is_fill_allowed(target_url, page_url, VISIT) is is_allowed

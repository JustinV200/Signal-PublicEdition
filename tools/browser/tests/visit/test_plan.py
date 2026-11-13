"""Tests for browser_tool.visit.plan: a bad target refuses the whole plan before launch."""

import pytest

from browser_tool.config import TOOL_ROOT, load_settings
from browser_tool.policy import HostPolicy
from browser_tool.visit import MAX_TARGETS, PlanError, parse_plan

MOODLE_PAGE = "https://lms.example.edu/mod/assign/index.php?id=1001"


def _policy(name: str) -> HostPolicy:
    """The shipped example checker config's policy."""
    policy = load_settings(TOOL_ROOT / f"browser-checker-{name}.example.toml").policy
    return HostPolicy.from_strings(policy.allow, policy.deny, is_allow_all=policy.allow_all)


def _plan(*urls: str, site: str = "moodle") -> dict:
    return {"targets": [{"key": f"p{i}", "url": url, "site": site} for i, url in enumerate(urls)]}


def test_a_plan_on_the_allowlist_passes():
    targets = parse_plan(_plan(MOODLE_PAGE), _policy("moodle"))
    assert [(t.key, t.url, t.site) for t in targets] == [("p0", MOODLE_PAGE, "moodle")]


@pytest.mark.parametrize(
    ("config", "plan"),
    [
        # The other launch's sign-in host is off this launch's allowlist.
        ("classroom", _plan("https://sso.example.edu/cas/login", site="classroom")),
        ("moodle", _plan("https://accounts.google.com/")),
        # One bad target among good ones refuses them all.
        ("moodle", _plan(MOODLE_PAGE, "https://lms.example.edu.evil.example/")),
        ("moodle", _plan("http://lms.example.edu/")),
        ("moodle", _plan("https://user@lms.example.edu/")),
        ("moodle", _plan(*[MOODLE_PAGE] * (MAX_TARGETS + 1))),
        ("moodle", {"targets": []}),
        ("moodle", {"targets": [{"key": "a", "url": MOODLE_PAGE, "site": "moodle"}] * 2}),
        ("moodle", {"targets": [{"key": "../a", "url": MOODLE_PAGE, "site": "moodle"}]}),
        (
            "moodle",
            {
                "targets": [
                    {"key": "a", "url": MOODLE_PAGE, "site": "moodle"},
                    {"key": "b", "url": MOODLE_PAGE, "site": "classroom"},
                ]
            },
        ),
        ("moodle", [MOODLE_PAGE]),
    ],
    ids=[
        "cas-from-classroom",
        "google-from-moodle",
        "lookalike",
        "http",
        "userinfo",
        "too-many",
        "empty",
        "repeated-key",
        "bad-key",
        "two-sites",
        "not-an-object",
    ],
)
def test_a_bad_plan_is_refused(config, plan):
    with pytest.raises(PlanError):
        parse_plan(plan, _policy(config))

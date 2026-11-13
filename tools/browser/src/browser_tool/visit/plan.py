"""The visit plan: up to MAX_TARGETS fixed pages for one site, checked before Edge starts.

The plan file is `{"targets": [{"key": ..., "url": ..., "site": ...}, ...]}`, written
by the checker from its courses.py. Every URL must be https, have no userinfo and be
allowed by this launch's policy, or the whole plan is refused: a lookalike host or a
host from the other launch's config never gets as far as a navigation.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from browser_tool.policy import HostPolicy, origin_of

MAX_TARGETS = 12
# Keys and site names: short slugs, so they're safe in logs and the out file.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PLAN_SCHEME = "https"


class PlanError(ValueError):
    """The plan is malformed or names a URL this launch may not visit."""


@dataclass(frozen=True)
class Target:
    """One page to visit: its key (unique in the plan), its URL and its site."""

    key: str
    url: str
    site: str


def parse_plan(data: object, policy: HostPolicy) -> tuple[Target, ...]:
    """The plan's targets, in order, after checking every one against policy.

    Raises:
        PlanError: On a malformed plan, more than MAX_TARGETS targets, a repeated
            key, more than one site, or a URL that isn't https, has userinfo or
            isn't allowed by policy.
    """
    if not isinstance(data, dict) or not isinstance(data.get("targets"), list):
        raise PlanError('the plan must be {"targets": [...]}')
    entries = data["targets"]
    if not 1 <= len(entries) <= MAX_TARGETS:
        raise PlanError(f"the plan must have 1 to {MAX_TARGETS} targets, not {len(entries)}")
    targets = tuple(_parse_target(entry, policy) for entry in entries)
    if len({target.key for target in targets}) != len(targets):
        raise PlanError("the plan repeats a key")
    if len({target.site for target in targets}) != 1:
        raise PlanError("the plan's targets must all be for one site")
    return targets


def _parse_target(entry: object, policy: HostPolicy) -> Target:
    """One checked target. Raises PlanError (see parse_plan)."""
    if not isinstance(entry, dict) or set(entry) != {"key", "url", "site"}:
        raise PlanError("each target must be exactly {key, url, site}")
    key, url, site = entry["key"], entry["url"], entry["site"]
    if not all(isinstance(value, str) for value in (key, url, site)):
        raise PlanError("a target's key, url and site must be strings")
    if not SLUG.fullmatch(key) or not SLUG.fullmatch(site):
        raise PlanError(f"bad key or site in target {key!r}")
    try:
        parts = urlsplit(url)
        has_userinfo = parts.username is not None or parts.password is not None
    except ValueError:
        raise PlanError(f"target {key!r} has a bad URL") from None
    if parts.scheme != PLAN_SCHEME or has_userinfo or not parts.hostname:
        raise PlanError(f"target {key!r} must be a plain https URL")
    decision = policy.check_url(url)
    if not decision.is_allowed:
        raise PlanError(f"target {key!r}: {origin_of(url)} is not allowed ({decision.reason})")
    return Target(key=key, url=url, site=site)

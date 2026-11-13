"""Turn a HostPolicy into Chromium's --host-resolver-rules launch flag.

Why this exists: Playwright's request routing only sees the FIRST url of a
redirect chain ("The handler will only be called for the first url if the
response is a redirect", BrowserContext.route docs, verified on 1.64). Mapping
blocked hosts to ~NOTFOUND in the browser's resolver stops every hop, including
redirects, before any request is sent. Verified on Edge 155: the blocked hop
never reaches the server, for names, IP literals and localhost alike.

Known gap: Chromium checks EXCLUDE rules before MAP rules, so a deny pattern that
sits inside an allowed wildcard (allow "*.x.com", deny "bad.x.com") is enforced
by routing for direct requests but not at DNS level for redirect hops. The
request guard still detects such hops after the fact. Also, with a system proxy
the proxy resolves names, so these rules don't apply.
"""

from browser_tool.policy.host_policy import HostPolicy

FLAG_NAME = "--host-resolver-rules"
_BLOCK_TARGET = "~NOTFOUND"


def build_host_resolver_rules(policy: HostPolicy) -> str | None:
    """Build the rule string for `policy`, or None when nothing needs blocking.

    Args:
        policy: The allow/deny policy.

    Returns:
        e.g. "MAP bad.com ~NOTFOUND, MAP * ~NOTFOUND, EXCLUDE good.com", or None for
        allow-all with an empty denylist and no guest block. A policy with a guest
        block (docker jobs) starts with its names and the host's IPs.
    """
    guest_hosts = policy.guest_block.resolver_hosts() if policy.guest_block else []
    rules = [f"MAP {host} {_BLOCK_TARGET}" for host in guest_hosts]
    rules.extend(f"MAP {pattern} {_BLOCK_TARGET}" for pattern in policy.deny_patterns)
    if not policy.is_allow_all:
        rules.append(f"MAP * {_BLOCK_TARGET}")
        rules.extend(f"EXCLUDE {pattern}" for pattern in policy.allow_patterns)
    return ", ".join(rules) if rules else None


def build_resolver_args(policy: HostPolicy) -> list[str]:
    """Return the browser launch args that enforce `policy` at DNS level (maybe empty)."""
    rules = build_host_resolver_rules(policy)
    return [f"{FLAG_NAME}={rules}"] if rules else []

"""The school's SSO patterns visit mode matches against (checker-v2.md section 3.1).

They come from the launch config's [visit] sso_host and school_domain, so the code
names no school. They back the Classroom launch's belt-and-braces cookie clear and
its "Google sent the account to SSO" check; the Classroom config's allowlist must
never name the SSO host itself.
"""

import re

# Matches nothing: an empty sso_host or school_domain turns its check off.
NEVER = re.compile(r"(?!)")


def _host_or_subdomain(host: str) -> re.Pattern[str]:
    """host itself or any subdomain of it, exactly; NEVER if host is empty."""
    if not host:
        return NEVER
    return re.compile(r"(^|\.)" + re.escape(host.lower().strip(".")) + "$")


def school_cookie_domain(school_domain: str) -> re.Pattern[str]:
    """Every school cookie: host-only ones ("sso.example.edu") and domain ones (".example.edu")."""
    return _host_or_subdomain(school_domain)


def sso_host_pattern(sso_host: str) -> re.Pattern[str]:
    """The SSO login host (or a subdomain of it) as a pattern."""
    return _host_or_subdomain(sso_host)

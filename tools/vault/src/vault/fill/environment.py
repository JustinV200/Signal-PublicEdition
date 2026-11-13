"""Refuse to fill when any debug logging could be on, because Playwright's logs carry fill values.

Playwright's driver uses the `debug` package: DEBUG accepts wildcards (`*`,
`pw*`) that turn on pw:protocol / pw:channel, which write raw protocol
messages (fill values included) to stderr or to DEBUG_FILE. Matching
patterns is easy to get wrong, so any non-empty DEBUG or DEBUG_FILE refuses,
as does PWDEBUG (the inspector). The driver reads them at launch; this
process's environment is the best available signal.
"""

import os
from collections.abc import Mapping

UNSAFE_VARS = ("DEBUG", "DEBUG_FILE", "PWDEBUG")


def playwright_debug_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return True if DEBUG, DEBUG_FILE or PWDEBUG is set to anything non-empty.

    Args:
        environ: The environment to check (default: os.environ).
    """
    env = os.environ if environ is None else environ
    return any(env.get(name, "").strip() for name in UNSAFE_VARS)

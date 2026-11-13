"""Clear Playwright's debug variables before the driver starts, whatever the backend.

The Playwright driver runs on this host for every backend, and it honours these
variables: DEBUG=pw:api would log fill("<value>") calls, typed secrets included.
"""

import logging
import os
from collections.abc import MutableMapping

logger = logging.getLogger(__name__)

DEBUG_ENV_VARS = ("DEBUG", "DEBUG_FILE", "PWDEBUG")


def clear_debug_env(environ: MutableMapping[str, str] = os.environ) -> list[str]:
    """Remove Playwright debug variables so the driver can't log action arguments.

    Args:
        environ: The environment to clean (the process environment by default).

    Returns:
        The names that were removed.
    """
    removed = [name for name in DEBUG_ENV_VARS if environ.pop(name, None) is not None]
    if removed:
        logger.warning("ignoring debug environment variables: %s", ", ".join(removed))
    return removed

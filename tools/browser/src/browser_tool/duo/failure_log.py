"""Logs a failure in a Duo event handler or background task: its type and stack frames only.

Both must swallow their errors (one would break Playwright's event dispatch, the
other would surface as "Task exception was never retrieved" with its message),
so this is how the failure is still seen. Never the message: like
server.tool_runner, messages can carry URLs with tokens.
"""

import logging
import traceback


def log_failure(log: logging.Logger, what: str, error: BaseException) -> None:
    """Log `error` as "<what> failed: <type>" plus its stack frames.

    Args:
        log: The calling module's logger.
        what: What was running, e.g. "Duo check".
        error: The exception caught.
    """
    frames = "".join(traceback.format_tb(error.__traceback__))
    log.error("%s failed: %s\n%s", what, type(error).__name__, frames)

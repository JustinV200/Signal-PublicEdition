"""The setup tool's health check: `browser-tool --check` validates the config as main does.

Loads the config and parses its host patterns ([policy] allow/deny, [duo]
code_relay_sites) the way the server does at start, so a config the server would
refuse fails here too. No browser, no MCP server, nothing written. The result is the
one-line {words, fix, command} summary of tools/setup/README.md ("Verify checks").
"""

from pathlib import Path

from browser_tool.config import ConfigError, Settings, load_settings
from browser_tool.policy import HostPolicy

EXIT_OK = 0
# The same code main exits with when the config stops the server.
EXIT_CONFIG_ERROR = 2
CONFIG_NAME = "tools/browser/browser.toml"
# Under the setup tool's 300-character cap on a summary field.
MAX_WORDS_CHARS = 200


def check_summary(path: Path | None = None) -> tuple[int, dict[str, str | None]]:
    """Load and validate the config, and describe what it allows.

    Args:
        path: The config file, as `--config` gives it; None means browser.toml.

    Returns:
        (exit code, {words, fix, command}): 0 when the server could start with it (an
        empty allowlist passes with a fix, since the browser runs but blocks every
        site), 2 when it couldn't.
    """
    try:
        settings = load_settings(path)
        _parse_host_patterns(settings)
    except (ConfigError, ValueError) as error:
        return EXIT_CONFIG_ERROR, _problem(error)
    policy = settings.policy
    if policy.allow_all:
        return EXIT_OK, _summary("config OK, every site allowed")
    if not policy.allow:
        fix = f"Add the sites it may open under [policy] allow in {CONFIG_NAME}."
        return EXIT_OK, _summary("config OK, but no site is allowed yet", fix)
    count = len(policy.allow)
    return EXIT_OK, _summary(f"config OK, {count} site{'s' if count != 1 else ''} allowed")


def _parse_host_patterns(settings: Settings) -> None:
    """Parse the patterns ActionContext.create and the Duo code relay parse at start.

    Raises:
        ValueError: A malformed pattern, as the server would report it.
    """
    HostPolicy.from_strings(settings.policy.allow, settings.policy.deny)
    try:
        HostPolicy.from_strings(settings.duo.code_relay_sites, ())
    except ValueError as error:
        raise ValueError(f"[duo] code_relay_sites: {error}") from error


def _problem(error: Exception) -> dict[str, str | None]:
    """The failing summary: one short line saying what's wrong."""
    # One short line: setup refuses a summary whose words break or run past its cap.
    words = "config problem: " + " ".join(str(error).split())
    if len(words) > MAX_WORDS_CHARS:
        words = words[: MAX_WORDS_CHARS - 1] + "…"
    return _summary(words, f"Fix {CONFIG_NAME}, then check again.")


def _summary(words: str, fix: str | None = None) -> dict[str, str | None]:
    """The summary object; there's never a command to run (the fix is an edit)."""
    return {"words": words, "fix": fix, "command": None}

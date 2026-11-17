"""Appends a signed-up API key to Signal's .env, after checking its name and value.

Only Python writes the key (never an agent), and only after every check passes.
Every Signal MCP server runs with `--env-file .env`, so a variable written here
reaches all of them. The name rules stop the signup (or a page steering it) from
hijacking them: the name must look like a credential (`*_KEY`, `*_TOKEN`), must
not start with a prefix that configures Python, uv, Node, git, the Claude CLI,
TLS or proxies, and must not already be set in .env or the process environment.
The value can't contain a line break, quote, `:` or `/`, so it can't add a
second line or pass as a URL.
"""

import os
import re
from pathlib import Path

from signal_jsonstate import state_lock

ENV_FILE_NAME = ".env"
# Next to .env, so `.env.*` in .gitignore already covers it.
ENV_LOCK_NAME = ".env.lock"
ENV_VAR_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
# _API_KEY ends in _KEY, so these two suffixes cover the three allowed endings.
CREDENTIAL_SUFFIXES = ("_KEY", "_TOKEN")
# Prefixes that change how Signal's servers run. "HTTP" covers HTTP_ and HTTPS_;
# "PYTHON" covers PYTHONPATH, PYTHONHOME and friends. GH_ and GITHUB_ are added
# beside GIT_ since gh and git read their tokens. SIGNAL_ and CHAMBER_ configure
# Signal's own tools, OTEL_ the CLI's telemetry export.
RESERVED_PREFIXES = (
    *("PATH", "PYTHON", "SSL_", "REQUESTS_", "CURL_", "UV_", "PIP_"),
    *("ANTHROPIC_", "CLAUDE_", "NODE_", "GIT_", "GH_", "GITHUB_", "HTTP"),
    *("SIGNAL_", "CHAMBER_", "OTEL_"),
)
# Proxy variables (HTTPS_PROXY, ALL_PROXY, ...) anywhere in the name.
RESERVED_INFIX = "PROXY"
# API keys are printable tokens: no spaces, quotes, `#`, `:`, `/` or line breaks.
KEY_PATTERN = re.compile(r"[A-Za-z0-9._~+=\-]{8,512}")
# A .env line that sets NAME: `NAME=v`, `NAME = v`, `export NAME=v` or a bare `export NAME`.
_ASSIGNMENT = re.compile(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|$)")


class EnvFileError(ValueError):
    """A bad variable name or key value, or the variable is already set."""


def is_allowed_env_var(name: str) -> bool:
    """True if `name` is an UPPER_SNAKE credential name that's safe to add.

    It must end in _KEY or _TOKEN, start with no RESERVED_PREFIXES, not contain
    PROXY, and not be set in this process's environment (case-insensitively, as
    Windows treats it). Whether .env already sets it is has_env_var's job.
    """
    return (
        ENV_VAR_PATTERN.fullmatch(name) is not None
        and name.endswith(CREDENTIAL_SUFFIXES)
        and not name.startswith(RESERVED_PREFIXES)
        and RESERVED_INFIX not in name
        and name.upper() not in {key.upper() for key in os.environ}
    )


def has_env_var(env_file: Path, name: str) -> bool:
    """True if `env_file` already sets `name`, case-insensitively as Windows reads env
    names (a missing file sets nothing)."""
    if not env_file.is_file():
        return False
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _ASSIGNMENT.match(line)
        if match and match.group(1).upper() == name.upper():
            return True
    return False


def append_env_var(env_file: Path, name: str, value: str) -> None:
    """Append `name=value` as its own line, holding the .env lock.

    Raises:
        EnvFileError: The name or value is bad, or the name is already set.
        signal_jsonstate.StateFileError: The lock couldn't be taken.
        OSError: The file can't be written.
    """
    if not is_allowed_env_var(name):
        raise EnvFileError(f"env var name {name!r} isn't allowed")
    if KEY_PATTERN.fullmatch(value) is None:
        raise EnvFileError("the key doesn't look like an API key")  # never echo the value
    with state_lock(env_file.with_name(ENV_LOCK_NAME)):
        if has_env_var(env_file, name):
            raise EnvFileError(f"{name} is already set")
        existing = env_file.read_bytes() if env_file.is_file() else b""
        lead = "" if not existing or existing.endswith(b"\n") else "\n"
        with env_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{lead}{name}={value}\n")

"""Paths holding secrets voice must never read: env files, token folders, browser data, credentials.

Two layers use the lists below. The CLI deny rules (SECRET_READ_DENY_RULES,
passed by sdk_options.py) block plain reads before the gate is asked. Reads
they miss, such as the 8.3 name "ENV~1" for ".env", reach the gate, which
refuses them through targets_secret after resolving the alias. Voice has no
shell, write or web-fetch tools, so reads are the only way it could reach one.
"""

import fnmatch
from collections.abc import Mapping
from pathlib import Path

from audiohub.brain.permissions.tool_paths import (
    relative_parts,
    resolve_path,
    target_paths,
)

# tools/sessions keeps a copy of the four lists below for managed sessions
# (claude_sessions/sdk/secret_rules.py). Change both together. The one
# difference is on purpose: ".claude/projects" (session transcripts) is only
# here, since managed sessions keep their auto-memory under it.
# Names (fnmatch, case-folded) of secret files at any depth.
SECRET_NAME_PATTERNS = (".env", ".env.*", "*.env")
# Folders whose contents are secret at any depth: tools/mail/.state, and
# tools/audiohub/.cache (the Spotify token and the IPC token) among them.
SECRET_DIRS = (".state", ".cache")
# Folders, relative to the project root, whose contents are secret: the browser
# profile, and screenshots of the owner's pages.
SECRET_PROJECT_DIRS = ("tools/browser/.profile", "tools/browser/.screenshots")
# Files and folders, relative to the home folder, holding credentials: SSH keys,
# Claude Code's login tokens, its IDE lock files (each holds an auth token),
# tools/vault's store (%LOCALAPPDATA%\signal-vault, see tools/vault paths.py),
# git, GitHub CLI, AWS, npm, Docker, Kubernetes, Azure and gcloud credentials,
# Claude Code's session transcripts, and the owner's real browser profiles (Edge,
# Chrome, Firefox, Brave: saved passwords and cookies).
# shortcut: the vault entry assumes LOCALAPPDATA is the default ~/AppData/Local;
# derive it from the variable if a profile ever moves it.
SECRET_HOME_PATHS = (
    ".ssh",
    ".claude/.credentials.json",
    ".claude/ide",
    "AppData/Local/signal-vault",
    ".git-credentials",
    ".config/gh",
    "AppData/Roaming/GitHub CLI",
    ".aws",
    ".npmrc",
    ".docker/config.json",
    "AppData/Local/Microsoft/Edge/User Data",
    "AppData/Local/Google/Chrome/User Data",
    "AppData/Roaming/Mozilla/Firefox/Profiles",
    "AppData/Local/BraveSoftware",
    ".claude/projects",
    ".kube",
    ".azure",
    "AppData/Roaming/gcloud",
    ".config/gcloud",
)

# The same lists as CLI permission rules: gitignore patterns relative to cwd,
# or to home for "~/". The CLI applies Read rules to Grep and Glob too.
SECRET_READ_DENY_RULES = (
    *(f"Read(**/{pattern})" for pattern in SECRET_NAME_PATTERNS),
    *(f"Read(**/{folder}/**)" for folder in SECRET_DIRS),
    *(f"Read(./{folder}/**)" for folder in SECRET_PROJECT_DIRS),
    # A home entry may be a file or a folder, so each gets both rules.
    *(rule for path in SECRET_HOME_PATHS for rule in (f"Read(~/{path})", f"Read(~/{path}/**)")),
)

# Shown to Claude as the tool result of a refused secret read.
SECRET_READ_REFUSAL = (
    "Voice never reads secrets or paths it can't check safely. Don't try another way "
    "to read this one."
)

# Case-folded, as relative_parts gives a path's parts.
_SECRET_PROJECT_DIR_PARTS = tuple(
    tuple(folder.casefold().split("/")) for folder in SECRET_PROJECT_DIRS
)
_SECRET_HOME_PARTS = tuple(tuple(path.casefold().split("/")) for path in SECRET_HOME_PATHS)


def _starts_with_any(parts: tuple[str, ...], prefixes: tuple[tuple[str, ...], ...]) -> bool:
    """Whether `parts` begins with one of the prefixes (each a tuple of path parts)."""
    return any(parts[: len(prefix)] == prefix for prefix in prefixes)


def _is_home_secret(path: str, root: Path) -> bool:
    """Whether a path, resolved from root, lies in one of the SECRET_HOME_PATHS."""
    resolved = resolve_path(path, root)
    # Resolved is absolute, so relative_parts only uses home to measure from.
    home_parts = relative_parts(resolved, Path.home()) if resolved else None
    return home_parts is not None and _starts_with_any(home_parts, _SECRET_HOME_PARTS)


def is_secret(path: str, root: Path) -> bool:
    """Say whether a path, once resolved, is a secret file or lies in a secret folder.

    Args:
        path: An absolute or relative path, as a tool call sent it.
        root: The project folder; relative paths are taken from here.

    Returns:
        True for a secret path, and also for one that can't be trusted (fails
        closed). Every part is checked, so a ".env" folder counts too.
    """
    parts = relative_parts(path, root)
    if parts is None:
        return True
    if any(part in SECRET_DIRS for part in parts):
        return True
    if any(fnmatch.fnmatchcase(part, p) for part in parts for p in SECRET_NAME_PATTERNS):
        return True
    return _starts_with_any(parts, _SECRET_PROJECT_DIR_PARTS) or _is_home_secret(path, root)


def targets_secret(tool_name: str, tool_input: Mapping[str, object], root: Path) -> bool:
    """Say whether any path a tool call targets is secret.

    Args:
        tool_name: The tool's name.
        tool_input: The tool's input as Claude sent it.
        root: The project folder.

    Returns:
        True if at least one targeted path is secret (see is_secret).
    """
    return any(is_secret(path, root) for path in target_paths(tool_name, tool_input))

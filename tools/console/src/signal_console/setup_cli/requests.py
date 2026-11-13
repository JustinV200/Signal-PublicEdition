"""Turn a setup wizard request from the page into a fixed `setup` CLI command line.

The page never names a program or a free argument list: it names one command from
COMMANDS and its fields, and this builds the argv (a list, never a shell string). Ids
are checked by shape and can't start with '-', so nothing is read as a flag; free text
goes in `--flag=value` form or on stdin. The setup CLI then validates ids against its
registry (exit 2 for an unknown one).
"""

import re
from dataclasses import dataclass
from typing import Any

# Tool and step ids in tools/setup's registry: lowercase words joined by '-'.
_REGISTRY_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
# Setting ids: a key, or `<file>:<key>` for a placeholder the schema doesn't name.
_SETTING_ID = re.compile(r"^[^\-=\x00-\x1f][^=\x00-\x1f]{0,199}$")
_CONTROL = re.compile(r"[\x00-\x1f]")
MAX_VALUE_CHARS = 1000
MAX_PATH_CHARS = 500
MAX_PATHS = 50
# Commands that only read (no progress, config or files written), keyed by command name.
READ_ONLY = frozenset({"intro", "list", "plan", "status", "tour", "prereqs"})
# Under the server's 64 KB body cap, with room for the JSON around it.
MAX_PASTE_CHARS = 60_000
SAMPLE_KINDS = ("email", "writing", "message", "code")
SAMPLE_ACTIONS = ("files", "paste", "mail", "keep", "count")
MARK_STATUSES = ("done", "skipped")


class SetupRequestError(ValueError):
    """The request names an unknown command or a field of the wrong shape (a 400)."""


@dataclass(frozen=True)
class SetupCall:
    """One setup CLI run: its arguments after `setup`, and text for its stdin (or None).

    `exclusive` is False only for read-only commands, which may run beside anything;
    every command that writes progress, config or files runs one at a time.
    """

    args: list[str]
    stdin: str | None = None
    exclusive: bool = True


def check_registry_id(body: dict[str, Any], field: str) -> str:
    """body[field] as a registry tool or step id. Raises SetupRequestError otherwise."""
    value = body.get(field)
    if not isinstance(value, str) or not _REGISTRY_ID.match(value):
        raise SetupRequestError(f"{field} must be a tool or step id")
    return value


def _id_list(body: dict[str, Any], field: str) -> list[str]:
    value = body.get(field, [])
    if not isinstance(value, list):
        raise SetupRequestError(f"{field} must be a list of tool ids")
    return [check_registry_id({field: item}, field) for item in value]


def _line(value: Any, field: str, limit: int = MAX_VALUE_CHARS) -> str:
    """A one-line string up to `limit` characters."""
    if not isinstance(value, str) or len(value) > limit or _CONTROL.search(value):
        raise SetupRequestError(f"{field} must be one line of at most {limit} characters")
    return value


def _apply(body: dict[str, Any]) -> list[str]:
    args = ["apply", check_registry_id(body, "tool"), check_registry_id(body, "step")]
    answer = body.get("answer")
    if answer is not None:
        if answer not in ("yes", "no"):
            raise SetupRequestError("answer must be yes or no")
        args.append(f"--answer={answer}")
    if body.get("value") is not None:
        args.append(f"--value={_line(body['value'], 'value')}")
    return args


def _config(body: dict[str, Any]) -> list[str]:
    tool, values = check_registry_id(body, "tool"), body.get("set")
    if values is None:
        return ["config", tool, "--list"]
    if not isinstance(values, dict) or not values:
        raise SetupRequestError("set must be an object of setting id to value")
    for setting_id in values:
        if not _SETTING_ID.match(setting_id):
            raise SetupRequestError(f"bad setting id {setting_id!r}")
    return ["config", tool, *(f"--set={k}={_line(v, k)}" for k, v in values.items())]


def _samples(body: dict[str, Any]) -> SetupCall:
    action, kind = body.get("action"), body.get("kind", "writing")
    if action not in SAMPLE_ACTIONS or kind not in SAMPLE_KINDS:
        raise SetupRequestError("unknown samples action or kind")
    extra, stdin = [], None
    if action == "files":
        paths = body.get("paths")
        if not isinstance(paths, list) or not 0 < len(paths) <= MAX_PATHS:
            raise SetupRequestError(f"paths must list 1 to {MAX_PATHS} files or folders")
        extra = [_line(p, "path", MAX_PATH_CHARS) for p in paths]
        if any(not p.strip() or p.startswith("-") for p in extra):
            raise SetupRequestError("a path can't be empty or start with '-'")
    elif action == "keep":
        numbers = body.get("numbers")
        if not isinstance(numbers, list) or not all(type(n) is int and n > 0 for n in numbers):
            raise SetupRequestError("numbers must be a list of positive whole numbers")
        extra = [str(n) for n in numbers]
    elif action == "paste":
        stdin = body.get("text")
        if not isinstance(stdin, str) or not stdin.strip() or len(stdin) > MAX_PASTE_CHARS:
            raise SetupRequestError(f"text must be 1 to {MAX_PASTE_CHARS} characters")
        if "\x00" in stdin:
            raise SetupRequestError("text can't hold NUL")
    return SetupCall(["samples", action, *extra, f"--kind={kind}"], stdin, action != "count")


def _joined(command: str, ids: list[str], flag: str = "") -> list[str]:
    """`command [flag] a,b` when ids were given, else just `command`."""
    return [command, *([flag] if flag else []), ",".join(ids)] if ids else [command]


def build_call(body: dict[str, Any]) -> SetupCall:
    """The setup CLI call a wizard request asks for.

    Args:
        body: The request JSON: {command, ...that command's fields}.

    Returns:
        The argv after `setup` and any stdin text.

    Raises:
        SetupRequestError: Unknown command or a malformed field.
    """
    command = body.get("command")
    fixed = {
        "intro": ["intro"],
        "list": ["list"],
        "plan": ["plan"],
        "status": ["status", "--json"],
        "tour": ["tour", "--json"],
        "wire": ["wire", "--yes"],
    }
    if isinstance(command, str) and command in fixed:
        return SetupCall(fixed[command], exclusive=command not in READ_ONLY)
    builders = {
        "prereqs": lambda: _joined("prereqs", _id_list(body, "tools"), "--tools"),
        "verify": lambda: _joined("verify", _id_list(body, "tools")),
        "choose": lambda: ["choose", ",".join(_id_list(body, "tools"))],
        "apply": lambda: _apply(body),
        "mark": lambda: _mark(body),
        "config": lambda: _config(body),
    }
    if command == "samples":
        return _samples(body)
    if not isinstance(command, str) or command not in builders:
        raise SetupRequestError("unknown setup command")
    args = builders[command]()
    # `config <tool> --list` and the samples count only read too.
    reads = command in READ_ONLY or args[-1] == "--list"
    return SetupCall(args, exclusive=not reads)


def _mark(body: dict[str, Any]) -> list[str]:
    status = body.get("status")
    if status not in MARK_STATUSES:
        raise SetupRequestError("status must be done or skipped")
    return ["mark", check_registry_id(body, "tool"), check_registry_id(body, "step"), status]

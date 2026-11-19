"""The ledger of what `setup wire` itself added to Claude Code's config: .setup/ledger.json.

Wire takes out or replaces an entry only when the ledger lists it and the config still
holds it exactly as recorded (merge.py). Every other entry in those files is the owner's
and stays as it is, whatever .setup/progress.json says about its tool. Entries setup wrote
before the ledger existed aren't in it, so they count as the owner's too.

Shape: {"servers": {name: entry}, "enabled": [server name], "allow": [rule],
        "hooks": [{"event": ..., "matcher": ..., "hook": {...}}], "statusline": {...} or null}
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from signal_setup import progress

LEDGER_FILE = Path(".setup") / "ledger.json"


@dataclass(frozen=True)
class Ledger:
    """What setup added, each entry exactly as it was written.

    Attributes:
        servers: The .mcp.json `mcpServers` entries, by name.
        enabled: The names added to settings.local.json's `enabledMcpjsonServers`.
        allow: The rules added to its `permissions.allow`.
        hooks: The hooks added to its `hooks`, each {"event", "matcher", "hook"}: the
            event, its group's matcher ("" for none) and the one hook entry.
        statusline: The `statusLine` written to the user's own settings, or None.
    """

    servers: dict[str, Any] = field(default_factory=dict)
    enabled: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)
    hooks: list[dict[str, Any]] = field(default_factory=list)
    statusline: dict[str, Any] | None = None


def _is_hook_record(value: Any) -> bool:
    """True for {"event": str, "matcher": str, "hook": {...}}."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("event"), str)
        and isinstance(value.get("matcher"), str)
        and isinstance(value.get("hook"), dict)
    )


def _parse(raw: Any) -> Ledger:
    """`raw` (the file's JSON) as a Ledger. Raises TypeError or ValueError on any other shape."""
    ledger = Ledger(**raw)
    is_valid = (
        isinstance(ledger.servers, dict)
        and isinstance(ledger.enabled, list)
        and isinstance(ledger.allow, list)
        and all(isinstance(text, str) for text in (*ledger.enabled, *ledger.allow))
        and isinstance(ledger.hooks, list)
        and all(_is_hook_record(record) for record in ledger.hooks)
        and isinstance(ledger.statusline, dict | None)
    )
    if not is_valid:
        raise ValueError("not a ledger")
    return ledger


def load(root: Path) -> Ledger:
    """The saved ledger, or an empty one when there is none or it can't be read.

    Empty on purpose, not an error: it then says setup added nothing, so wire takes nothing
    out. The worst a lost ledger does is leave setup's old entries in place as the owner's.
    """
    try:
        return _parse(json.loads((root / LEDGER_FILE).read_text("utf-8")))
    except (OSError, ValueError, TypeError, RecursionError):  # deep nesting overflows the parser
        return Ledger()


def save(root: Path, ledger: Ledger) -> None:
    """Write the ledger, unless the file already says the same.

    So a wire that adds nothing, with nothing recorded before, leaves no file behind.
    """
    if ledger != load(root):
        progress.write_state(root / LEDGER_FILE, asdict(ledger))

"""Who listens on the console's port, in words, for the setup window's fallback line. Read-only.

When `console open` fails, the launcher says why in one line; the usual cause is
another checkout's console on the same port (both default to 8790). Setup is
stdlib only and can't use the console's own check (tools stay standalone), so
this asks PowerShell, as the console's register.ps1 does: the socket table and
the listener's and its parent's exe paths (uv's venv launcher starts the base
Python as a child, so the venv path is on the parent). Nothing connects to the
port, so no key or token goes to whatever holds it. Windows only.
"""

import json
import re
import subprocess
from pathlib import Path

# A listener on these addresses blocks a 127.0.0.1 bind; prints {pid, name, paths} as JSON.
HOLDER_SCRIPT = r"""
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in '127.0.0.1', '0.0.0.0', '::' } | Select-Object -First 1
if (-not $listener) { return }
$holderId = $listener.OwningProcess
$holder = Get-CimInstance Win32_Process -Filter "ProcessId = $holderId"
$parent = if ($holder) {
    Get-CimInstance Win32_Process -Filter "ProcessId = $($holder.ParentProcessId)"
}
$paths = @(@($holder, $parent) | Where-Object { $_ } |
    ForEach-Object { $_.ExecutablePath } | Where-Object { $_ })
ConvertTo-Json -Compress @{ pid = $holderId; name = [string]$holder.Name; paths = $paths }
"""
LOOKUP_TIMEOUT_S = 20
# A checkout's console runs from <checkout>\tools\console\.venv.
CONSOLE_VENV = re.compile(r"^(.+?)\\tools\\console\\\.venv\\", re.IGNORECASE)


def port_holder_words(port: int, root: Path) -> str | None:
    """Who holds `port`, when it isn't this checkout's own console.

    Args:
        port: The console's port.
        root: This checkout's repo root.

    Returns:
        "another checkout's console, <its folder>", or "<program> (pid N)"; None when
        the port is free, this checkout's console holds it, or the lookup fails.
    """
    holder = _read_holder(port)
    if holder is None:
        return None
    paths = [path for path in holder.get("paths") or [] if isinstance(path, str)]
    own_venv = str(root / "tools" / "console" / ".venv").casefold() + "\\"
    if any(path.casefold().startswith(own_venv) for path in paths):
        return None
    for path in paths:
        match = CONSOLE_VENV.match(path)
        if match:
            return f"another checkout's console, {match.group(1)}"
    return f"{holder.get('name') or 'another program'} (pid {holder.get('pid')})"


def _read_holder(port: int) -> dict | None:
    # `port` is an int, so it can't change the script. A failed lookup only costs the
    # detail: the caller still says the window couldn't open.
    script = f"$Port = {int(port)}\n{HOLDER_SCRIPT}"
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=LOOKUP_TIMEOUT_S)
        holder = json.loads(result.stdout) if result.stdout.strip() else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return holder if isinstance(holder, dict) else None

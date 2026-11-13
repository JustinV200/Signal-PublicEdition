"""Runs INSIDE a container (fed to `python3 -I -` on stdin): list processes as JSON lines.

For every process: pid, name, uid, NoNewPrivs, Seccomp mode, effective
capabilities, the start of its command line, and "userns": "same" if it shares
this script's user namespace (the container's), "other" if it is in another
one (Chromium's sandbox makes its own, where CapEff counts only inside it), or
"unreadable" (root's and non-dumpable processes). /proc/<pid>/status and
cmdline stay readable even for a non-dumpable process, so this works as "edge".
Stdlib only, because the guest image has nothing else.
"""

import json
import os

STATUS_FIELDS = ("Name", "Uid", "NoNewPrivs", "Seccomp", "CapEff")
CMDLINE_PREVIEW_CHARS = 80
OWN_USERNS = os.readlink("/proc/self/ns/user")


def user_namespace(pid: str) -> str:
    """'same', 'other' or 'unreadable', relative to this script's user namespace."""
    try:
        return "same" if os.readlink(f"/proc/{pid}/ns/user") == OWN_USERNS else "other"
    except PermissionError:
        return "unreadable"


def describe(pid: str) -> dict[str, str]:
    """The STATUS_FIELDS of one process plus a short command line and its userns."""
    info = {"pid": pid, "userns": user_namespace(pid)}
    with open(f"/proc/{pid}/status", encoding="utf-8") as status:
        for line in status:
            key, _, value = line.partition(":")
            if key in STATUS_FIELDS:
                info[key] = value.split()[0] if key == "Uid" else value.strip()
    with open(f"/proc/{pid}/cmdline", "rb") as cmdline:
        info["cmd"] = (
            cmdline.read().replace(b"\0", b" ").decode(errors="replace")[:CMDLINE_PREVIEW_CHARS]
        )
    return info


if __name__ == "__main__":
    for entry in sorted(os.listdir("/proc")):
        if not entry.isdigit():
            continue
        try:
            print(json.dumps(describe(entry)))
        except FileNotFoundError:
            continue  # the process exited while we were listing

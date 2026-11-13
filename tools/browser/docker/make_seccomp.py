"""Build seccomp.json for the browser container from Docker's default profile.

Used to build the docker backend's guest (see README.md). Docker's default allows
clone, unshare, setns and chroot only to containers holding CAP_SYS_ADMIN or
CAP_SYS_CHROOT, and those gates are fixed when the container is created. The
browser container runs with --cap-drop=ALL, so Chromium's namespace sandbox
(which needs all four) would be filtered and Edge would refuse to start. This
script appends one unconditional rule for exactly those four syscalls and
changes nothing else, so the result is easy to diff against upstream.

Usage: python make_seccomp.py <upstream default.json> <output seccomp.json>
The upstream file is moby/profiles seccomp/default.json at the version the
running engine vendors (see README.md).
"""

import json
import sys
from pathlib import Path

SANDBOX_SYSCALLS = ["clone", "unshare", "setns", "chroot"]
SANDBOX_RULE = {
    "names": SANDBOX_SYSCALLS,
    "action": "SCMP_ACT_ALLOW",
    "comment": "Chromium's namespace sandbox, without CAP_SYS_ADMIN (tools/browser/docker)",
}


def add_sandbox_rule(profile: dict) -> dict:
    """Return a copy of `profile` with the sandbox rule appended.

    Raises:
        ValueError: If the input doesn't look like a seccomp profile.
    """
    if not isinstance(profile.get("syscalls"), list) or "defaultAction" not in profile:
        raise ValueError("not a seccomp profile: missing defaultAction or syscalls")
    return {**profile, "syscalls": [*profile["syscalls"], SANDBOX_RULE]}


def main(argv: list[str]) -> int:
    """Read the upstream profile, add the rule, write the output file."""
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    upstream = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    text = json.dumps(add_sandbox_rule(upstream), indent=1) + "\n"
    # newline="\n": the same bytes on Windows and Linux, matching .gitattributes.
    Path(argv[2]).write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

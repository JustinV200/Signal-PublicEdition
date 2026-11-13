"""Pulls the user's own recent sent emails as writing samples, through the mail tool's CLI.

Only the user's own words are kept: quoted replies, forwarded parts and signatures-after-
"--" are cut. Short emails are dropped (too little voice). Nothing is saved until the
user picks which candidates to keep.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from signal_setup.samples.store import save_sample

CANDIDATES_FILE = Path(".setup") / "mail-candidates.json"
MAIL_CLI = ["uv", "run", "--project", "tools/mail", "--frozen", "--no-sync", "mail"]
SENT_QUERY = "in:sent newer_than:365d"
MIN_WORDS = 30
WRAPPER = re.compile(r"</?untrusted_email_content>")
# Where a reply's quoted part begins: "On <date> <name> wrote:", Outlook's header block, a forward.
QUOTE_START = re.compile(
    r"^(On .+wrote:\s*$|-{2,}\s*Original Message|From: .+|-{2,} Forwarded message|--\s*$)",
    re.MULTILINE,
)


def own_text(body: str) -> str:
    """The part of an email the sender wrote: no wrapper tags, quoted reply or '> ' lines."""
    body = WRAPPER.sub("", body)
    match = QUOTE_START.search(body)
    if match:
        body = body[: match.start()]
    return "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith(">")).strip()


def _mail_json(root: Path, *args: str) -> Any:
    """Run a mail CLI command and parse its JSON. Raises ValueError with its error line."""
    result = subprocess.run([*MAIL_CLI, *args], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise ValueError(lines[-1] if lines else "mail failed")
    return json.loads(result.stdout)


def fetch_sent(root: Path, account: str = "personal", limit: int = 25) -> list[dict[str, str]]:
    """Recent sent emails long enough to sample, saved as candidates.

    Raises ValueError when the mail tool fails.
    """
    candidates = []
    for summary in _mail_json(root, "search", account, SENT_QUERY, "--max", str(limit)):
        message = _mail_json(root, "read", account, str(summary["id"]))
        text = own_text(str(message.get("body", "")))
        if len(text.split()) >= MIN_WORDS:
            subject = WRAPPER.sub("", str(message.get("subject", ""))).strip()
            candidates.append({"subject": subject, "text": text})
    path = root / CANDIDATES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidates, indent=2), "utf-8")
    return candidates


def save_candidates(root: Path, keep: list[int]) -> list[str]:
    """Save the 1-based picks from the last fetch, then delete the candidates file."""
    path = root / CANDIDATES_FILE
    candidates = json.loads(path.read_text("utf-8"))
    saved = [
        save_sample(root, "email", c["subject"] or "sent", c["text"]).name
        for number, c in enumerate(candidates, 1)
        if number in keep
    ]
    path.unlink()
    return saved

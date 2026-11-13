"""The guided samples step in the terminal: files, pasted text and sent mail, with a count.

Every source is optional, and the whole step can be skipped. The voice check after it
(rewriting a paragraph in the user's voice) is done by Claude through the copytone skill.
"""

from pathlib import Path

from signal_setup.samples.extract import import_paths
from signal_setup.samples.sent_mail import fetch_sent, save_candidates
from signal_setup.samples.store import TARGET_RANGE, sample_count, save_sample
from signal_setup.terminal import TerminalAsker

PASTE_END = "END"


def _from_files(root: Path, asker: TerminalAsker) -> None:
    """Import files or folders the user names."""
    raw = asker.text("File or folder paths (separate with ';')")
    if raw:
        paths = [Path(p.strip().strip('"')) for p in raw.split(";") if p.strip()]
        kind = asker.text("What kind are they: email, writing, message or code?") or "writing"
        for line in import_paths(root, paths, kind):
            asker.say(line)


def _from_paste(root: Path, asker: TerminalAsker) -> None:
    """Take pasted text, ended by a line saying END."""
    kind = asker.text("What kind is it: email, writing, message or code?") or "message"
    asker.say(f"Paste it, then type {PASTE_END} on its own line:")
    lines = []
    while (line := input()) != PASTE_END:
        lines.append(line)
    asker.say(f"added {save_sample(root, kind, 'pasted', chr(10).join(lines)).name}")


def _from_mail(root: Path, asker: TerminalAsker) -> None:
    """Show recent sent emails and save the ones the user keeps."""
    try:
        candidates = fetch_sent(root)
    except ValueError as error:
        asker.say(f"Couldn't read sent mail: {error}")
        return
    for number, candidate in enumerate(candidates, 1):
        preview = " ".join(candidate["text"].split())[:90]
        asker.say(f"{number:2}. {candidate['subject'][:50]}: {preview}")
    keep = asker.text("Numbers to keep (e.g. 1 3 4), 'all', or Enter for none") or ""
    picks = (
        list(range(1, len(candidates) + 1))
        if keep.strip() == "all"
        else [int(t) for t in keep.replace(",", " ").split() if t.isdigit()]
    )
    for name in save_candidates(root, picks):
        asker.say(f"added {name}")


def collect(root: Path, mail_ready: bool) -> int:
    """Loop over the sample sources until the user is done. Returns the sample count."""
    asker = TerminalAsker()
    low, high = TARGET_RANGE
    sources = {"f": _from_files, "p": _from_paste, "m": _from_mail}
    while True:
        asker.say(
            f"\nSamples so far: {sample_count(root)} (aim for {low}-{high}: some emails, "
            "some longer writing, some casual messages)."
        )
        menu = "f = files, p = paste" + (", m = your sent mail" if mail_ready else "")
        choice = (asker.text(f"Add more? {menu}") or "").lower()
        if choice not in sources or (choice == "m" and not mail_ready):
            return sample_count(root)
        try:
            sources[choice](root, asker)
        except (OSError, ValueError) as error:
            asker.say(f"Skipped: {error}")

"""Turn the voice hub's status lines into its phase and the console's voice feed.

audiohub's StatusLine (loop/status.py) prints `[HH:MM:SS.t] label: detail`.
The phases are the Phase enum's values (loop/conversation/routing/routes.py). A
"heard" line carries the full transcript, a "speaking" line the first spoken
text cut to 90 characters, each quoted and followed by timings in brackets:
  [14:02:15.2] heard: "Hey Claude, what's the time?" (2.1 s audio, stt 85 ms)
  [14:02:16.0] speaking: "It's two o'clock." (+1 more) (kernel 12 ms)
An "ignored" line (speech with no wake phrase) follows its "heard" line, so
the feed can drop that speech. Python logging ERROR and CRITICAL lines become
"error: ..." notes; other output (INFO logging, tracebacks) is skipped.
"""

import re
from dataclasses import dataclass

PHASES = frozenset({"listening", "thinking", "speaking"})
HEARD_LABEL = "heard"
SPEAKING_LABEL = "speaking"
IGNORED_LABEL = "ignored"
# Labels worth a line in the feed beside what was heard and said.
NOTE_LABELS = frozenset(
    {"ready", "stopping", "barge-in", "cancelled", "permission", "awaiting answer"}
)

_STATUS_LINE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\.\d\] ([^:]+?)(?:: (.*))?$")
_ERROR_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} [\d:,]+ (?:ERROR|CRITICAL) \S+: (.*)$")
# A quoted text followed by any number of " (...)" timing groups. Greedy, so the
# closing quote is the last one (the timing groups contain none).
_QUOTED = re.compile(r'^"(.*)"(?: \([^()]*\))*$')


@dataclass(frozen=True)
class HubLine:
    """What one status line tells the console.

    Attributes:
        phase: The hub's new phase, if the line announces one.
        kind: "heard", "said" or "note" if it belongs in the voice feed, "ignored" if
            the speech just heard had no wake phrase, else None.
        text: The feed text (the transcript or spoken text, unquoted).
    """

    phase: str | None
    kind: str | None
    text: str


def parse_hub_line(line: str) -> HubLine | None:
    """Parse one line of hub output; None for lines that say nothing to the console."""
    line = line.rstrip("\r\n")
    error = _ERROR_LINE.match(line)
    if error is not None:
        return HubLine(None, "note", f"error: {error.group(1)}")
    match = _STATUS_LINE.match(line)
    if match is None:
        return None
    label, detail = match.group(1), match.group(2) or ""
    phase = label if label in PHASES else None
    if label == IGNORED_LABEL:
        return HubLine(None, "ignored", detail)
    if label == HEARD_LABEL:
        return HubLine(None, "heard", _unquote(detail))
    if label == SPEAKING_LABEL and detail:
        return HubLine(phase, "said", _unquote(detail))
    if label in NOTE_LABELS:
        return HubLine(phase, "note", f"{label}: {detail}" if detail else label)
    return HubLine(phase, None, "") if phase else None


def _unquote(detail: str) -> str:
    match = _QUOTED.match(detail)
    return match.group(1) if match else detail

"""Where the brief keeps its state: tools/brief/.state/ (gitignored), and sleepmode's flag.

Producers depend only on signal_brief, never on tools/brief, so the default state
folder comes from this file's place in the repo
(packages/brief/src/signal_brief/paths.py), which holds because uv installs the
package in editable mode. Tests pass their own BriefPaths.
"""

from dataclasses import dataclass
from pathlib import Path

# parents: [0] signal_brief, [1] src, [2] brief, [3] packages, [4] the repo
REPO_ROOT: Path = Path(__file__).resolve().parents[4]
DEFAULT_STATE_DIR: Path = REPO_ROOT / "tools" / "brief" / ".state"
# sleepmode's state file; only its is_asleep flag is read.
SLEEPMODE_STATE_FILE: Path = REPO_ROOT / "tools" / "sleepmode" / ".state" / "state.json"


@dataclass(frozen=True)
class BriefPaths:
    """Every state file of the brief.

    Attributes:
        state_dir: The folder holding them all.
        sleep_state: sleepmode's state.json.
    """

    state_dir: Path = DEFAULT_STATE_DIR
    sleep_state: Path = SLEEPMODE_STATE_FILE

    @property
    def events(self) -> Path:
        """The event log, one JSON entry per line."""
        return self.state_dir / "events.jsonl"

    @property
    def lock(self) -> Path:
        """The log's lock file, which guards every state file."""
        return self.state_dir / "events.lock"

    @property
    def counters(self) -> Path:
        """seq, per-letter ref counts, the delivery count and the last compaction."""
        return self.state_dir / "counters.json"

    @property
    def bookmark(self) -> Path:
        """The newest seq the owner has seen (`through`)."""
        return self.state_dir / "bookmark.json"

    @property
    def away(self) -> Path:
        """The away flag, its end and note."""
        return self.state_dir / "away.json"

    @property
    def presence(self) -> Path:
        """last_human_at, the due brief and the morning rule's day."""
        return self.state_dir / "presence.json"

    @property
    def shown(self) -> Path:
        """The last deliveries and their acks."""
        return self.state_dir / "shown.json"

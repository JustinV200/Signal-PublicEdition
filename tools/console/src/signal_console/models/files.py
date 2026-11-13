"""`ModelFiles`: every file the model strip reads or writes, passed in so tests use tmp copies."""

from dataclasses import dataclass
from pathlib import Path

from signal_console.paths import (
    BRAIN_CHOICE_PATH,
    LOCAL_SETTINGS_PATH,
    MODELS_LOCK_FILE,
    SESSION_MODELS_FILE,
    SETTINGS_BACKUP_FILE,
)


@dataclass(frozen=True)
class ModelFiles:
    """Where the model picks and the sessions' current models live.

    Attributes:
        settings: .claude/settings.local.json (the orchestrator's next-session pick).
        backup: Its copy from before the console's last write.
        session_models: {session_id: {model, at}}, written by the session hook.
        brain_choice: Voice's pick (signal_modelchoice's format).
        lock: Held while a pick is written, so two clicks can't interleave.
    """

    settings: Path
    backup: Path
    session_models: Path
    brain_choice: Path
    lock: Path

    @classmethod
    def for_repo(cls, state_dir: Path) -> "ModelFiles":
        """The real files: the repo's settings and voice's pick, the rest in `state_dir`."""
        return cls(
            settings=LOCAL_SETTINGS_PATH,
            backup=state_dir / SETTINGS_BACKUP_FILE,
            session_models=state_dir / SESSION_MODELS_FILE,
            brain_choice=BRAIN_CHOICE_PATH,
            lock=state_dir / MODELS_LOCK_FILE,
        )

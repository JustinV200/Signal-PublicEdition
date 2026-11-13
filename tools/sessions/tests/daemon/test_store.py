"""SessionStore pruning: old finished records are dropped on save, live ones never are."""

from pathlib import Path

from claude_sessions.daemon.session import SessionRecord, SessionState, SessionStore
from claude_sessions.daemon.session.store import MAX_STORED_SESSIONS


def _record(index: int, state: SessionState) -> SessionRecord:
    return SessionRecord(
        id=f"s-{index:08x}",
        repo_name="Demo",
        repo_path="C:/Demo",
        claude_session_id=f"c-{index}",
        model=None,
        permission_mode="default",
        state=state,
        created_at=index,
        updated_at=index,
    )


def test_save_keeps_the_newest_records_and_every_live_one(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.json")
    old_live = _record(0, SessionState.IDLE)
    finished = [_record(i, SessionState.STOPPED) for i in range(1, MAX_STORED_SESSIONS + 6)]

    store.save([old_live, *finished])

    kept_ids = {record.id for record in store.load()}
    newest = {record.id for record in finished[-MAX_STORED_SESSIONS:]}
    assert kept_ids == newest | {old_live.id}

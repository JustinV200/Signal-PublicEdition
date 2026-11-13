"""Public API of whiteboard.agent: the board agent, a Claude session that reacts to board changes.

The daemon builds it with create_board_agent() and hands its
on_board_changed() to the change watcher.
"""

from pathlib import Path

from signal_confirm import confirm

from whiteboard.agent.board_agent import (
    DEFAULT_TURN_TIMEOUT_S,
    BoardAgent,
    ListItems,
    LoadingIndicator,
    LookWithProjection,
    TurnSession,
)
from whiteboard.agent.board_change import BoardChange, merge_changes
from whiteboard.agent.permissions import DIALOG_CAPTION, PermissionRouter, is_auto_allowed
from whiteboard.agent.triage import Triage, TriageDecision, ask_sdk
from whiteboard.agent.turn_message import image_block, stream_message

# How long the owner has to answer a permission dialog before it counts as No.
PERMISSION_TIMEOUT_S = 120.0


def create_board_agent(
    model: str,
    repo_root: Path,
    list_items: ListItems,
    triage: Triage | None = None,
    look: LookWithProjection | None = None,
    loading: LoadingIndicator | None = None,
    turn_timeout_s: float = DEFAULT_TURN_TIMEOUT_S,
) -> BoardAgent:
    """Build the production board agent: SDK session plus signal_confirm permission dialogs.

    Args:
        model: Model alias or id for the session (config `agent.model`).
        repo_root: The repo root, used as the session's working directory.
        list_items: Gives the scene items currently projected.
        triage: Optional cheap pre-check run before each turn.
        look: Optional projection-visible photo; enables the verify turn after a draw.
        loading: Optional "thinking" placeholder shown while a turn runs.
        turn_timeout_s: Seconds before a hung turn is given up (config `agent.turn_timeout_s`).

    Returns:
        A BoardAgent; call start() on the daemon's event loop.
    """
    # Imported here so importing this package doesn't load the SDK (tests, the CLI).
    from whiteboard.agent.sdk_session import SdkTurnSession

    # confirm() blocks, which is fine: the router calls it on a worker thread.
    router = PermissionRouter(
        lambda question: confirm(DIALOG_CAPTION, question, timeout_s=PERMISSION_TIMEOUT_S)
    )
    session = SdkTurnSession(model, repo_root, router)
    return BoardAgent(
        session,
        list_items,
        allow_snapshot_read=router.allow_snapshot_read,
        triage=triage,
        look=look,
        loading=loading,
        turn_timeout_s=turn_timeout_s,
    )


__all__ = [
    "PERMISSION_TIMEOUT_S",
    "BoardAgent",
    "BoardChange",
    "LoadingIndicator",
    "PermissionRouter",
    "Triage",
    "TriageDecision",
    "TurnSession",
    "ask_sdk",
    "create_board_agent",
    "image_block",
    "is_auto_allowed",
    "merge_changes",
    "stream_message",
]

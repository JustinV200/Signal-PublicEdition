"""The wording of the voice notifications a managed session sends to the hub.

Written for the ear: one or two short sentences, no paths or code. The source
is "session:<repo name>" so the hub's kernel can tell sessions apart.
"""

from signal_hub_notify import MAX_SOURCE_CHARS, HubNote

from claude_sessions.text import first_sentences, truncate

SOURCE_PREFIX = "session:"
# Sentences of the final reply that are read out when a turn finishes.
SUMMARY_SENTENCES = 2
MAX_SUMMARY_CHARS = 300
MAX_DETAIL_CHARS = 200


def source_for(repo_name: str) -> str:
    """The hub source for a repo's session, cut to the hub's 64-character limit.

    Args:
        repo_name: The repo folder name, e.g. "OtherRepo".

    Returns:
        "session:<repo name>".
    """
    return f"{SOURCE_PREFIX}{repo_name}"[:MAX_SOURCE_CHARS]


def turn_finished_note(repo_name: str, final_reply: str) -> HubNote:
    """A normal-priority note that a turn finished, with the start of the reply.

    Args:
        repo_name: The session's repo.
        final_reply: Claude's final reply text for the turn ("" when there was none).

    Returns:
        E.g. "OtherRepo session finished: Tests pass. I pushed the fix."
    """
    summary = first_sentences(final_reply, SUMMARY_SENTENCES, MAX_SUMMARY_CHARS)
    text = (
        f"{repo_name} session finished: {summary}" if summary else f"{repo_name} session finished."
    )
    return HubNote(source_for(repo_name), text, "normal")


def session_failed_note(repo_name: str, detail: str) -> HubNote:
    """A high-priority note that a session's turn or process failed.

    Args:
        repo_name: The session's repo.
        detail: A short reason, e.g. "the Claude CLI exited".

    Returns:
        E.g. "OtherRepo session hit an error: the Claude CLI exited."
    """
    reason = truncate(detail, MAX_DETAIL_CHARS) or "unknown error"
    return HubNote(source_for(repo_name), f"{repo_name} session hit an error: {reason}", "high")


def approval_needed_note(repo_name: str, description: str) -> HubNote:
    """A high-priority note that a session is waiting for the owner's approval.

    Only the description's first line (the headline) is spoken; the raw
    command or path is in the dialog.

    Args:
        repo_name: The session's repo.
        description: The approval description (see approvals.describe_tool_call).

    Returns:
        E.g. "OtherRepo session needs approval: Claude wants to run git push. Answer the
        dialog on the PC."
    """
    headline = truncate(description.splitlines()[0] if description else "", MAX_DETAIL_CHARS)
    what = f": {headline.rstrip('.')}." if headline else "."
    text = f"{repo_name} session needs approval{what} Answer the dialog on the PC."
    return HubNote(source_for(repo_name), text, "high")

"""brief_injection: step 4 of the prompt hook, what (if anything) to add about the brief.

On "full" a session gets the brief once per due brief, not once per brief id: the
id changes with every append, and re-injecting on each one while a brief is due
would repeat it all day. The injection is a delivery (so its cut and refs are
known for the ack), recorded with the session id and the due brief it answers. It
never acks by itself. While the brief is still due nothing has acked it (an ack
drops the due brief), so Claude was busy and replied about something else: it's
injected again an hour after the session's last injection. Once an ack drops the
due brief, the 6 h gap one-liner comes from on_interaction's own "one_liner" offer.
"""

from datetime import datetime, timedelta

from signal_brief import (
    BRIEF_TAG,
    MAX_HOOK_CHARS,
    Brief,
    BriefPaths,
    DeliveryOrigin,
    load_deliveries,
    on_interaction,
    one_liner_text,
    record_delivery,
    render_model,
    to_iso,
)
from signal_untrusted import framed

from brief_tool.surface import SESSION
from brief_tool.wording import HOOK_BRIEF_LINE, ONE_LINER_LINE

# An unacked injection is offered again this long after the last one.
REINJECT_AFTER = timedelta(hours=1)


def brief_injection(paths: BriefPaths, session_id: str, now: datetime) -> tuple[str, str | None]:
    """Run on_interaction for a present prompt and build what to inject.

    Args:
        paths: The brief's state files.
        session_id: This Claude session's id.
        now: The time of the prompt.

    Returns:
        A decision for the log, and the text to inject (None for nothing).

    Raises:
        BriefLogError: The brief's state couldn't be read or written.
    """
    interaction = on_interaction(paths, now)
    brief = interaction.brief
    if interaction.offer == "one_liner":
        return _one_liner(brief)
    if interaction.offer != "full" or interaction.due is None:
        return "none", None
    due = to_iso(interaction.due.marked_at)
    given = [
        d for d in load_deliveries(paths) if d.session_id == session_id and d.due_marked_at == due
    ]
    if given and now - max(d.at for d in given) < REINJECT_AFTER:
        return "full:already", None
    render = render_model(brief, MAX_HOOK_CHARS, titles_only=True)
    if not render.shown:
        return _one_liner(brief)
    delivery = record_delivery(paths, brief, render, DeliveryOrigin(SESSION, session_id, due), now)
    return "full", framed(HOOK_BRIEF_LINE.format(delivery_id=delivery.id), render.body, BRIEF_TAG)


def _one_liner(brief: Brief) -> tuple[str, str]:
    """The one-liner's decision and injected text."""
    return "one_liner", ONE_LINER_LINE.format(text=one_liner_text(brief))

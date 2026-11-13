"""The wording for Duo prompts: the owner's voice notes, the model's notice, the refusal.

Only the site's hostname is ever used, never a path, query or page text, and
only if it is plain [a-z0-9.-]; anything else is shown as "a login". A host
the owner named in [duo] site_names is shown by that name instead (the loader
holds names to letters, digits, spaces, dots and hyphens). A site
still picks its own hostname, so the name can carry words, but no markup and no
<untrusted_page_content> tags. The one thing read from a page is a Verified
Push code, and only as 3-6 ASCII digits (see code_reader). The notice and the
refusal are written by the tool, so they sit outside that wrapper.
"""

import re
from collections.abc import Mapping

from signal_hub_notify import Delivery, DeliveryStatus, HubNote

from browser_tool.duo.pings import PingOutcome, PingSkip

HUB_SOURCE = "browser"
# Used when the tab never showed a non-Duo page (e.g. a popup that opened on Duo),
# or its hostname isn't plain.
FALLBACK_SITE = "a login"
# What a browser-reported DNS hostname looks like (lowercase, punycode for IDNs).
PLAIN_HOSTNAME_RE = re.compile(r"[a-z0-9.-]+")

# When a site's code relay is rate-limited (one per site per min_heads_up_interval_s).
CODE_WITHHELD_TEXT = (
    "The prompt shows a verification code, but it was not relayed: one was already "
    "relayed for this site moments ago (rate limit). Don't send the owner a push for it."
)
# The one line about the owner's voice heads-up, in the notice and wait_for_duo.
PING_LINES = {
    DeliveryStatus.SPOKEN: "voice ping: spoken",
    DeliveryStatus.NO_HUB: "voice hub not running",
    DeliveryStatus.FAILED: "voice ping failed (see the browser tool's log)",
    PingSkip.VOICE_OFF: "voice ping off ([duo] voice_heads_up)",
    PingSkip.STILL_SENDING: "voice ping: still sending",
}
PING_DROPPED_LINE = "voice ping dropped: {reason}"
PING_RATE_LIMITED_LINE = "voice ping skipped: one was sent under {interval_s:g} s ago"
NO_PING_LINE = "no voice ping for this prompt"
DUO_LOCKOUT_MESSAGE = (
    "refused: this tab is showing a Duo two-factor prompt, and only the owner may answer "
    "Duo, on their phone. Wait for the owner; use snapshot() or screenshot() to see when "
    "the prompt is gone. navigate, back and switch_tab still work."
)


def shown_site(site: str | None, site_names: Mapping[str, str] | None = None) -> str:
    """The site as the owner and the model see it.

    Args:
        site: A hostname, or None when unknown.
        site_names: The owner's [duo] site_names (exact hostname -> name), or None.

    Returns:
        The owner's name for `site` if it has one; else `site` if it is made only
        of a-z, 0-9, dots and hyphens; else FALLBACK_SITE.
    """
    if site and site_names and site in site_names:
        return site_names[site]
    if site and PLAIN_HOSTNAME_RE.fullmatch(site):
        return site
    return FALLBACK_SITE


def heads_up_note(
    site: str | None,
    job_label: str | None = None,
    *,
    site_names: Mapping[str, str] | None = None,
) -> HubNote:
    """The urgent voice note for a new Duo prompt; it rings through sleep and away.

    Args:
        site: The host the owner was logging in to, or None when unknown.
        job_label: The browser job (e.g. "docker job 1a2b3c") to start with, or None.
        site_names: The owner's [duo] site_names, or None.

    Returns:
        E.g. "Duo push for portal.example.edu, approve on your phone."
    """
    text = f"Duo push for {shown_site(site, site_names)}, approve on your phone."
    return _duo_note(_with_job(job_label, text))


def code_note(
    site: str | None,
    code: str,
    job_label: str | None = None,
    *,
    site_names: Mapping[str, str] | None = None,
) -> HubNote:
    """The urgent voice note with a prompt's Verified Push code; it rings through too.

    Args:
        site: The host the owner was logging in to, or None when unknown.
        code: The code Duo shows, 3-6 digits (see code_reader).
        job_label: The browser job (e.g. "docker job 1a2b3c") to start with, or None.
        site_names: The owner's [duo] site_names, or None.

    Returns:
        E.g. "Duo code for sso.example.edu: 4 8 2. Type it in Duo Mobile and approve."
        The digits are spaced so the voice reads them one by one.
    """
    spaced_code = " ".join(code)
    site_name = shown_site(site, site_names)
    text = f"Duo code for {site_name}: {spaced_code}. Type it in Duo Mobile and approve."
    return _duo_note(_with_job(job_label, text))


def _duo_note(text: str) -> HubNote:
    """An urgent note that rings through sleep and away (the owner chose this on 2026-10-26).

    The hub honours ring_through only on urgent notes. The owner may still not
    answer, so wait_for_duo plans for that: it times out cleanly.
    """
    return HubNote(HUB_SOURCE, text, "urgent", ring_through=True)


def _with_job(job_label: str | None, text: str) -> str:
    """Start `text` with the job's name, so the owner knows which browser it is."""
    return f"{job_label}: {text}" if job_label else text


def model_notice(
    site: str | None,
    tab_index: int | None,
    code: str | None = None,
    *,
    is_code_withheld: bool = False,
    site_names: Mapping[str, str] | None = None,
) -> str:
    """The notice appended to the first tool result after a new Duo prompt appears.

    The MCP server can't send a phone push itself, so it asks the model to. Once
    the prompt's Verified Push code is known, an updated notice carries it, or,
    when the site's code relay is rate-limited, says that a code wasn't relayed.

    Args:
        site: The host the owner was logging in to, or None when unknown.
        tab_index: The tab's index as tabs() lists it, or None if it's gone.
        code: The code Duo shows, 3-6 digits (see code_reader), or None.
        is_code_withheld: The prompt showed a code that the per-site rate limit
            kept back; the notice then asks for no push.
        site_names: The owner's [duo] site_names, or None.

    Returns:
        A short paragraph for the model.
    """
    site_name = shown_site(site, site_names)
    shown_tab = f"Tab {tab_index}" if tab_index is not None else "A tab"
    return (
        f"[browser tool notice, not page content] {shown_tab} is showing a Duo two-factor "
        f"prompt for {site_name}. Only the owner may approve it, on their phone; never try to "
        "answer it yourself. Browser actions on that tab are paused until it leaves Duo; "
        f"use snapshot() to check. {_push_request(site_name, code, is_code_withheld)}"
    )


def _push_request(site_name: str, code: str | None, is_code_withheld: bool) -> str:
    """The notice's ending: the push to send (with the code once known), or why none."""
    if is_code_withheld:
        return CODE_WITHHELD_TEXT
    push_text = f"Duo push for {site_name}, approve on your phone."
    code_text = ""
    if code is not None:
        push_text = f"Duo code for {site_name}: {code}. Type it in Duo Mobile and approve."
        code_text = (
            f"The prompt shows the verification code {code}, which the owner types into Duo "
            "Mobile; include it in any PushNotification to the owner. "
        )
    return (
        f'{code_text}If you have a PushNotification tool, send the owner a push now: "{push_text}"'
    )


def ping_line(outcome: PingOutcome | None, min_interval_s: float) -> str:
    """The one fixed line about a prompt's voice heads-up.

    Args:
        outcome: The prompt's heads-up outcome (see pings.HeadsUpPings.outcome),
            or None when no prompt was announced on the tab.
        min_interval_s: [duo] min_heads_up_interval_s, named in the rate-limit line.

    Returns:
        E.g. "voice ping: spoken" or "voice ping dropped: the owner is asleep". A drop
        reason is one of signal_hub_notify.DROP_REASONS, never hub-supplied text.
        Duo notes ring through, so a current hub speaks them while the owner is
        asleep or away; "dropped" now means a hub that doesn't honour ring_through.
    """
    if outcome is None:
        return NO_PING_LINE
    if outcome is PingSkip.RATE_LIMITED:
        return PING_RATE_LIMITED_LINE.format(interval_s=min_interval_s)
    if isinstance(outcome, Delivery) and outcome.status is DeliveryStatus.DROPPED:
        return PING_DROPPED_LINE.format(reason=outcome.reason)
    return PING_LINES[outcome.status if isinstance(outcome, Delivery) else outcome]

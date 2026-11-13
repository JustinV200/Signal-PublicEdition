"""Speaks the run's message through the audiohub CLI (`audiohub notify`).

The runner calls this, never the model: the job has no audiohub tools at all. The
CLI exits 0 once the hub has queued the message and 1 if it wasn't delivered (hub
not running, message refused, connection failed); see
tools/audiohub/src/audiohub/cli/commands/notify.py.
"""

from mail_digest.child_env import run_hidden
from mail_digest.settings import AUDIOHUB_PROJECT, NOTIFY_PRIORITY, NOTIFY_SOURCE, NOTIFY_TIMEOUT_S


def notify_command(text: str, source: str = NOTIFY_SOURCE) -> list[str]:
    """The argv that speaks `text`, from source ("mail-digest" or "assignment-check").

    An argv list, so no shell parses the text; the `--` stops argparse reading a
    text that starts with "-" as an option.
    """
    return [
        "uv", "run", "--project", str(AUDIOHUB_PROJECT), "--frozen", "--no-sync",
        "audiohub", "notify",
        "--source", source,
        "--priority", NOTIFY_PRIORITY,
        "--", text,
    ]  # fmt: skip


def send_notify(text: str, source: str = NOTIFY_SOURCE) -> bool:
    """Send `text` to the hub once, from source. True only if the CLI exited 0 (queued).

    Never raises: a CLI that can't start, times out or fails is logged and is False,
    so the caller keeps the items to retry next run.
    """
    return run_hidden("audiohub notify", notify_command(text, source), NOTIFY_TIMEOUT_S)

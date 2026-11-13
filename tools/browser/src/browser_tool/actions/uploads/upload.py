"""The upload_file tool: send one local file through a page's file input or upload button.

Order of checks:
- the docker server refuses at once (ctx.uploads_allowed);
- the ref is prepared like a click's (Duo lockout first, origin, dialog and
  frame checks);
- the file is checked and read once (local_files.read_checked_file): only its bytes
  are handed to the page, so it can't be swapped after the check;
- the gate: uploading always runs the send rule ("uploading a file sends
  it"), plus the text rules on the target; a ref that isn't a file input is
  clicked to open its picker, so it also gets the whole click rule;
- the owner's dialog names the file and its size;
- right before acting the target is judged again and refused if it now asks
  more, or stopped or started being a file input; then ensure_ready_to_act
  (after_action.act_and_report), and again before a picker gets the file.
A file input gets the bytes directly (set_input_files). Anything else is
clicked and its picker, intercepted by session.FileChooserWatch (no native
picker ever opens), gets them.
"""

import asyncio

from playwright.async_api import FilePayload

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import (
    GatedAction,
    click_gate_check,
    confirm_or_log,
    ensure_not_stricter,
    gate_check,
)
from browser_tool.actions.guards import ensure_ready_to_act
from browser_tool.actions.local_files import read_checked_file
from browser_tool.actions.pointer import RefTarget, act_and_report, log_target, prepare_ref
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.config import CATEGORY_SEND, resolve_tool_path
from browser_tool.gates import GateCheck, strictest

BYTES_PER_MB = 1024 * 1024
UPLOAD_REASON = "uploading a file sends it"
UPLOADS_OFF = "refused: uploads are off in docker jobs"
# How long a clicked upload button gets to open its picker.
PICKER_WAIT_S = 5.0
NO_PICKER = (
    "clicked {label}, but no file picker opened, so nothing was uploaded; use the ref "
    "of a file input or an upload button"
)
TARGET_CHANGED = "refused: the element changed after it was checked; take a new snapshot"
# A <label> ref means its control.
FILE_INPUT_JS = """(el) => {
  const field = el.tagName === 'LABEL' && el.control ? el.control : el;
  return field.tagName === 'INPUT' && field.type === 'file';
}"""


async def upload_file(ctx: ActionContext, ref: str, path: str) -> str:
    """Upload the local file `path` through the element `ref` (a file input or upload button).

    Args:
        ctx: The action context.
        ref: The file input's or upload button's snapshot ref.
        path: The file's full path, inside an [uploads] root.

    Raises:
        ActionError: On the docker server, a refused file, a refused or
            declined upload, or a button that opened no picker.
    """
    if not ctx.uploads_allowed:
        raise ActionError(UPLOADS_OFF)
    target = await prepare_ref(ctx, ref)
    uploads = ctx.settings.uploads
    roots = [resolve_tool_path(root) for root in uploads.roots]
    upload = read_checked_file(path, roots, int(uploads.max_mb * BYTES_PER_MB))
    is_input = await target.locator.evaluate(FILE_INPUT_JS)
    check = await _judge(ctx, target, is_input, scroll_first=True)
    shown = f"{upload.name} ({len(upload.data)} bytes)"
    log = log_target("upload_file", ref, target.label)
    action = GatedAction(f"upload {shown} through {target.label}", log, target.frame_origin)
    approved_origin = await confirm_or_log(ctx, target.page, action, check)
    await _recheck(ctx, target, approved_origin, (is_input, check))
    payload: FilePayload = {"name": upload.name, "mimeType": upload.mime, "buffer": upload.data}

    async def act() -> None:
        if is_input:
            await target.locator.set_input_files(payload)
        else:
            await _through_picker(ctx, target, approved_origin, payload)

    done = f"uploaded {shown} through {wrap_untrusted(target.label)}"
    return await act_and_report(
        ctx, target.page, approved_origin, act, done, trigger=[target.label]
    )


async def _judge(
    ctx: ActionContext, target: RefTarget, is_input: bool, *, scroll_first: bool
) -> GateCheck | None:
    """The send rule, plus the text rules (a file input) or the click rule (anything else)."""
    send = ctx.rules.check(CATEGORY_SEND, UPLOAD_REASON)
    if is_input:
        return strictest(send, gate_check(ctx, [target.label], target.frame_origin))
    clicked = await click_gate_check(
        ctx, target.locator, target.label, target.frame_origin, scroll_first=scroll_first
    )
    return strictest(send, clicked)


async def _recheck(
    ctx: ActionContext,
    target: RefTarget,
    approved_origin: str | None,
    judged: tuple[bool, GateCheck | None],
) -> None:
    """Judge the target again right before the upload; refuse if anything changed for the worse.

    Raises:
        ActionError: If the tab moved, the ref is gone, it stopped or started
            being a file input, or the upload now asks more.
    """
    is_input, check = judged
    ensure_ready_to_act(ctx, target.page, approved_origin)
    if await target.locator.count() != 1:
        raise ActionError(TARGET_CHANGED)
    if await target.locator.evaluate(FILE_INPUT_JS) != is_input:
        raise ActionError(TARGET_CHANGED)
    ensure_not_stricter(check, await _judge(ctx, target, is_input, scroll_first=False))


async def _through_picker(
    ctx: ActionContext, target: RefTarget, approved_origin: str | None, payload: FilePayload
) -> None:
    """Click the upload button, and give the file to the picker it opens.

    Raises:
        ActionError: NO_PICKER if none opens within PICKER_WAIT_S, or
            ensure_ready_to_act's refusal right before the file is set.
    """
    choosers = ctx.session.file_choosers
    claim = choosers.claim(target.page)
    try:
        await target.locator.click()
        try:
            chooser = await asyncio.wait_for(claim, PICKER_WAIT_S)
        except TimeoutError:
            raise ActionError(NO_PICKER.format(label=wrap_untrusted(target.label))) from None
    finally:
        choosers.release(target.page)
    ensure_ready_to_act(ctx, target.page, approved_origin)
    await chooser.set_files(payload)

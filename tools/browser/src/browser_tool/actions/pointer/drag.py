"""The drag tool: drag one snapshot ref onto another (drag and drop).

Both ends are prepared like a click's ref (Duo lockout, origin and frame
checks) and both go through the click rules (gating.click_gate_check), so the
strictest of the two wins: dragging a message onto "Trash" asks as a delete,
and so does dragging a "Delete" handle anywhere. The dialog and the log name
both ends. Right before the drag both ends are judged again, and a drag that
now asks more than was approved is refused (after_action.recheck_refs); then
the last-moment check runs (after_action.act_and_report). There is no hover
settle: drag_to presses on the source at once.
"""

from browser_tool.actions.context import ActionContext
from browser_tool.actions.gating import GatedAction, click_gate_check, confirm_or_log
from browser_tool.actions.pointer.after_action import act_and_report, recheck_refs
from browser_tool.actions.pointer.target import log_target, prepare_ref
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.gates import strictest


async def drag(ctx: ActionContext, source: str, target: str) -> str:
    """Drag the element `source` onto the element `target` (both snapshot refs).

    Raises:
        ActionError: If either ref is stale or in a blocked frame, or the owner declined.
    """
    start = await prepare_ref(ctx, source)
    end = await prepare_ref(ctx, target)
    check = strictest(
        await click_gate_check(ctx, start.locator, start.label, start.frame_origin),
        await click_gate_check(ctx, end.locator, end.label, end.frame_origin),
    )
    frame_origin = start.frame_origin or end.frame_origin
    log = f"{log_target('drag', source, start.label)} {log_target('to', target, end.label)}"
    action = GatedAction(f"drag {start.label} to {end.label}", log, frame_origin)
    approved_origin = await confirm_or_log(ctx, start.page, action, check)
    await recheck_refs(ctx, [start, end], approved_origin, check)
    return await act_and_report(
        ctx,
        start.page,
        approved_origin,
        lambda: start.locator.drag_to(end.locator),
        f"dragged {wrap_untrusted(start.label)} to {wrap_untrusted(end.label)}",
        trigger=[start.label, end.label],
    )

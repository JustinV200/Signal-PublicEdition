"""BoardTools: the board_* MCP tool handlers, each a thin call to the daemon's JSON API.

Requests are blocking (urllib), so each runs in a worker thread to keep the
MCP event loop free. Daemon failures become ToolErrors the model can read.
The board_todo_* results carry plan text, some of it copied from email, so they
come back framed as data (whiteboard.todo.plan_data).
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, TypeVar

from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from signal_tasks import StateFileError

from whiteboard.config import CONSOLE_TASKS_FILE, USAGE_FILE
from whiteboard.daemon_client import (
    DaemonApi,
    DaemonApiError,
    DaemonConnection,
    DaemonStartError,
    FitMode,
    quad_from_numbers,
    send_fit,
)
from whiteboard.display.scene import IDLE_VIEW, LOADING_ID, NIGHT_VIEW, TODO_VIEW
from whiteboard.tasks_grid import draw_task_grid
from whiteboard.todo import plan_data

ItemKind = Literal["svg", "mermaid", "text", "markdown", "math", "rough", "image"]
LoadMode = Literal["replace", "overlay"]
# Mirrors whiteboard.saves.REFRESHERS (a Literal so the tool schema lists the choices).
Refresher = Literal["tasks", "todo"]
DEFAULT_HIGHLIGHT_S = 3.0

Result = TypeVar("Result")


class BoardTools:
    """Backs the board_* tools with one DaemonConnection.

    The parameter lists mirror the tool schemas in the design brief (board_draw
    takes eight), which is why they exceed the usual four-parameter limit.
    """

    def __init__(self, connection: DaemonConnection) -> None:
        """Args: connection: Finds or starts the daemon on first use."""
        self._connection = connection

    async def look(self, clean: bool = True, raw: bool = False) -> list[Image | str]:
        """Photograph the board; returns the PNG as image content plus a description."""
        result = await self._call(lambda api: api.look(clean, raw))
        return [Image(path=result["png_path"]), describe_look(result, clean)]

    async def draw(
        self,
        kind: ItemKind,
        content: str,
        x: float,
        y: float,
        w: float,
        h: float,
        id: str = "",
        style: dict[str, Any] | None = None,
    ) -> str:
        """Create or replace an item; returns its id."""
        item: dict[str, Any] = {"kind": kind, "content": content, "x": x, "y": y, "w": w, "h": h}
        if id:
            item["id"] = id
        if style:
            item["style"] = style
        result = await self._call(lambda api: api.put_item(item))
        return f"Drew {kind} item id={_item_id(result)} at x={x:g}, y={y:g}, w={w:g}, h={h:g}."

    async def move(self, id: str, x: float, y: float, w: float, h: float) -> str:
        """Move or resize an item."""
        await self._call(lambda api: api.patch_item(id, {"x": x, "y": y, "w": w, "h": h}))
        return f"Moved {id} to x={x:g}, y={y:g}, w={w:g}, h={h:g}."

    async def remove(self, id: str) -> str:
        """Remove one item."""
        await self._call(lambda api: api.delete_item(id))
        return f"Removed {id}."

    async def clear(self) -> str:
        """Remove every item."""
        await self._call(lambda api: api.clear())
        return "Cleared every projected item."

    async def placeholder(self, x: float, y: float, w: float, h: float) -> str:
        """Move or resize this turn's "Claude is thinking" box."""
        box = {"x": x, "y": y, "w": w, "h": h}
        try:
            await self._call(lambda api: api.patch_item(LOADING_ID, box))
        except ToolError:
            return "No loading box is showing right now; nothing to move."
        return f"Loading box moved to x={x:g}, y={y:g}, w={w:g}, h={h:g}."

    async def list_items(self) -> str:
        """List the projected items as JSON."""
        scene = await self._call(lambda api: api.scene())
        return json.dumps(scene.get("items", []), indent=1)

    async def highlight(
        self, x: float, y: float, w: float, h: float, seconds: float = DEFAULT_HIGHLIGHT_S
    ) -> str:
        """Flash a box on the board."""
        region = {"x": x, "y": y, "w": w, "h": h, "seconds": seconds}
        await self._call(lambda api: api.highlight(region))
        return f"Highlighted x={x:g}, y={y:g}, w={w:g}, h={h:g} for {seconds:g} s."

    async def calibrate(self) -> str:
        """Run calibration and board fitting."""
        result = await self._call(lambda api: api.calibrate())
        return describe_calibration(result)

    async def realign(self) -> str:
        """Re-align to the board now; returns what changed and the numbers."""
        return json.dumps(await self._call(lambda api: api.realign()))

    async def fit(self, mode: FitMode = "auto", quad: list[float] | None = None) -> str:
        """Fit, show or clear the board quad."""
        try:
            corners = quad_from_numbers(quad) if quad else None
        except ValueError as error:
            raise ToolError(str(error)) from error
        result = await self._call(lambda api: send_fit(api, mode, corners))
        return json.dumps(result)

    async def save(
        self,
        name: str,
        description: str = "",
        overwrite: bool = False,
        refresher: Refresher | None = None,
    ) -> str:
        """Save the projected items and the owner's ink under a name; returns the save's meta."""
        result = await self._call(
            lambda api: api.save_board(name, description, overwrite, refresher or "")
        )
        return json.dumps(result)

    async def load(self, name: str, mode: LoadMode = "replace", include_ink: bool = True) -> str:
        """Bring a saved board back onto the board; returns what was restored."""
        result = await self._call(lambda api: api.load_board(name, mode, include_ink))
        return json.dumps(result)

    async def list_saves(self) -> str:
        """List the saved boards as JSON, newest first."""
        result = await self._call(lambda api: api.list_saves())
        return json.dumps(result.get("saves", []), indent=1)

    async def delete_save(self, name: str) -> str:
        """Delete one saved board."""
        await self._call(lambda api: api.delete_save(name))
        return f"Deleted the saved board {name!r}."

    async def todo_show(self) -> str:
        """Switch to the TODO view (synced first); returns the sync summary as plan data."""
        return plan_data(await self._plan_call(lambda api: api.todo("show")))

    async def todo_hide(self) -> str:
        """Switch back to the projected items."""
        result = await self._call(lambda api: api.todo("hide"))
        # Under the night view the items wait under it, so say which view really shows.
        return f"The TODO view is off; the board shows the {result.get('view')} view."

    async def todo_sync(self) -> str:
        """Re-read life/ and update the TODO view; returns the sync summary as plan data."""
        return plan_data(await self._plan_call(lambda api: api.todo("sync")))

    async def todo_done(self, item: str) -> str:
        """Tick an item in its week plan; returns the sync summary as plan data."""
        return plan_data(await self._plan_call(lambda api: api.todo("done", item)))

    async def todo_undone(self, item: str) -> str:
        """Untick an item in its week plan; returns the sync summary as plan data."""
        return plan_data(await self._plan_call(lambda api: api.todo("undone", item)))

    async def tasks_show(self) -> str:
        """Clear the board and draw the task grid from the console's task list."""
        now = datetime.now().astimezone()
        try:
            return await self._call(
                lambda api: draw_task_grid(api, CONSOLE_TASKS_FILE, USAGE_FILE, now)
            )
        except StateFileError as error:
            raise ToolError(f"can't read the task list: {error}") from error

    async def night_show(self, sky: bool = True) -> str:
        """Show sleep mode's night view (tonight's sky, or black); returns the daemon's reply."""
        return json.dumps(await self._call(lambda api: api.night("show", sky)))

    async def night_hide(self) -> str:
        """Leave the night view for the view it hid; returns the view now showing."""
        return json.dumps(await self._call(lambda api: api.night("hide")))

    async def idle_show(self) -> str:
        """Switch to the idle view; returns what it shows, as counts."""
        return json.dumps(await self._call(lambda api: api.idle("show")))

    async def idle_hide(self) -> str:
        """Switch back to the projected items; returns the view now showing."""
        result = await self._call(lambda api: api.idle("hide"))
        return f"The idle view is off; the board shows the {result.get('view')} view."

    async def _plan_call(self, operation: Callable[[DaemonApi], Result]) -> Result:
        """Like _call, but a failure's message is framed as plan data too.

        A todo error can quote plan lines (the ambiguous matches, the line that
        changed, or a plan that can't be read), so it gets the same frame and escaping
        as a result.
        """
        try:
            return await self._call(operation)
        except ToolError as error:
            raise ToolError(plan_data({"ok": False, "error": str(error)})) from error

    async def _call(self, operation: Callable[[DaemonApi], Result]) -> Result:
        """Run a daemon operation in a worker thread, turning failures into ToolErrors."""
        try:
            return await asyncio.to_thread(self._connection.call, operation)
        except (DaemonApiError, DaemonStartError) as error:
            raise ToolError(str(error)) from error


def describe_look(result: Mapping[str, Any], clean: bool) -> str:
    """One paragraph about a look: size, coordinate space, and the projected items."""
    width, height = result.get("width"), result.get("height")
    view = "projection hidden (owner's ink only)" if clean else "projection visible"
    space = result.get("space") or "board coordinates"
    items = json.dumps(_brief_items(result.get("items", [])), separators=(",", ":"))
    # The daemon adds a note only when the photo is NOT in board_draw's space (uncalibrated).
    if result.get("note"):
        alignment = f" Note: {result['note']}"
    else:
        alignment = " Origin top-left, same space as board_draw."
    hidden = ""
    if result.get("view") == TODO_VIEW:
        hidden = " The TODO view is showing, so these items are hidden (board_todo_hide)."
    elif result.get("view") == IDLE_VIEW:
        hidden = " The idle view is showing, so these items are hidden (board_idle_hide)."
    elif result.get("view") == NIGHT_VIEW:
        hidden = " The night view is showing (sleep mode), so these items are hidden until it ends."
    return (
        f"Board photo {width}x{height} px, {view}, in {space}. Saved at "
        f"{result.get('png_path')}.{alignment} Projected items: {items}{hidden}"
    )


def describe_calibration(result: Mapping[str, Any]) -> str:
    """Summarize a calibration result for the model."""
    if not result.get("ok"):
        return f"Calibration failed: {result.get('error', 'unknown error')}"
    error_px = result.get("reprojection_error_px")
    board = "found and fitted" if result.get("board_found") else "not found (use board_fit)"
    return f"Calibrated (reprojection error {error_px} px). Board outline {board}."


def _item_id(result: Mapping[str, Any]) -> str:
    """Pull the id out of a create response ({"id"} or {"item": {"id"}})."""
    item = result.get("item", result)
    return str(item.get("id", "?"))


def _brief_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Id, kind and box of each item (content is left out to keep the text short)."""
    return [{key: item.get(key) for key in ("id", "kind", "x", "y", "w", "h")} for item in items]

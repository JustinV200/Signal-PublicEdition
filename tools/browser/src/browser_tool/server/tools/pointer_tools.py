"""The MCP tools that use the mouse: click, click_at, drag, hover and scroll.

Docstrings here are the descriptions the model reads.
"""

from mcp.server.mcpserver import MCPServer

from browser_tool import actions
from browser_tool.server.tool_runner import ToolRunner


def register_pointer_tools(server: MCPServer, runner: ToolRunner) -> None:
    """Register click, click_at, drag, hover and scroll on `server`."""
    tool = server.tool(structured_output=False)

    @tool
    async def click(
        ref: str, button: str = "left", double: bool = False, modifiers: list[str] | None = None
    ) -> str:
        """Click the element with this ref from the latest snapshot.

        button is "left", "right" or "middle"; double=true double-clicks;
        modifiers are keys held during the click (Alt, Control, Meta, Shift).
        Buying, paying, sending, deleting and similar clicks pause for the owner's
        approval in a dialog on their screen; a decline returns "not done".
        """
        args = (ref, button, double, modifiers or ())
        return await runner.run("click", actions.click, *args)

    @tool
    async def click_at(x: float, y: float) -> str:
        """Click a point in the viewport (CSS pixels from the top left), e.g. on a canvas.

        Prefer click(ref). The element at the point gets the same approval rules.
        """
        return await runner.run("click_at", actions.click_at, x, y)

    @tool
    async def drag(source: str, target: str) -> str:
        """Drag the element with ref `source` onto the element with ref `target`.

        Dropping onto Trash or dragging a Delete handle waits for the owner like a click.
        """
        return await runner.run("drag", actions.drag, source, target)

    @tool
    async def hover(ref: str) -> str:
        """Move the mouse over the element with this ref (opens hover menus and tooltips)."""
        return await runner.run("hover", actions.hover, ref)

    @tool
    async def scroll(ref: str | None = None, direction: str = "down", amount: float = 1) -> str:
        """Scroll the page, or the box holding this ref, by `amount` screens (up to 10).

        direction is up, down, left or right. It says where the view is and
        whether more content loaded at the end.
        """
        return await runner.run("scroll", actions.scroll, ref, direction, amount)

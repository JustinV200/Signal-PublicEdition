"""The MCP tools that move the tab or pick it: navigate, history, tabs and wait_for_duo.

Docstrings here are the descriptions the model reads.
"""

from mcp.server.mcpserver import MCPServer

from browser_tool import actions
from browser_tool.server.tool_runner import ToolRunner


def register_navigation_tools(server: MCPServer, runner: ToolRunner) -> None:
    """Register navigate, back, forward, reload, tabs, switch_tab, new_tab, close_tab
    and wait_for_duo on `server`."""
    tool = server.tool(structured_output=False)

    @tool
    async def navigate(url: str) -> str:
        """Open a URL in the current tab (https:// if no scheme), then call snapshot()."""
        return await runner.run("navigate", actions.navigate, url)

    @tool
    async def back() -> str:
        """Go back one page in the current tab."""
        return await runner.run("back", actions.back)

    @tool
    async def forward() -> str:
        """Go forward one page in the current tab."""
        return await runner.run("forward", actions.forward)

    @tool
    async def reload() -> str:
        """Reload the current tab.

        A reload, back or forward that would send a form again waits for the
        owner's approval like a send.
        """
        return await runner.run("reload", actions.reload)

    @tool
    async def tabs() -> str:
        """List open tabs with their index, URL and title."""
        return await runner.run("tabs", actions.list_tabs)

    @tool
    async def switch_tab(index: int) -> str:
        """Make the tab with this index (from tabs()) the current tab."""
        return await runner.run("switch_tab", actions.switch_tab, index)

    @tool
    async def new_tab(url: str) -> str:
        """Open a URL in a new tab and make it the current tab."""
        return await runner.run("new_tab", actions.new_tab, url)

    @tool
    async def close_tab(index: int) -> str:
        """Close the tab with this index (from tabs()). The only tab can't be closed."""
        return await runner.run("close_tab", actions.close_tab, index)

    @tool
    async def wait_for_duo(timeout_s: float = 90, wait_anyway: bool = False) -> str:
        """Wait for the owner to approve the Duo prompt on the current tab (read only).

        Call it when a result says a Duo prompt appeared. It never touches Duo.
        It says whether the owner's voice ping was spoken. The ping rings even
        while the owner is asleep or away, but they may not answer: plan for a
        timeout. If an older hub dropped it, it returns at once unless
        wait_anyway=true. timeout_s is capped at 300. On approval it reports
        where the tab landed.
        """
        return await runner.run("wait_for_duo", actions.wait_for_duo, timeout_s, wait_anyway)

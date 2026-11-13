"""The MCP tool that answers a page's dialog: answer_dialog.

Its docstring is the description the model reads.
"""

from mcp.server.mcpserver import MCPServer

from browser_tool import actions
from browser_tool.server.tool_runner import ToolRunner


def register_dialog_tools(server: MCPServer, runner: ToolRunner) -> None:
    """Register answer_dialog on `server`."""
    tool = server.tool(structured_output=False)

    @tool
    async def answer_dialog(accept: bool, text: str | None = None) -> str:
        """Answer the dialog (confirm, prompt or leave-page) open on the current tab.

        accept=true presses OK, accept=false presses Cancel. text answers a
        prompt (only with accept=true). While a dialog is open the tab is
        frozen and other actions on it are refused; results show the dialog.
        Accepting one that buys, sends or deletes waits for the owner's approval.
        """
        return await runner.run("answer_dialog", actions.answer_dialog, accept, text)

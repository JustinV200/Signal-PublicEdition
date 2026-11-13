"""Public API of browser_tool.server.tools: register_tools, the MCP tool list.

The tools are split by what they do: navigation_tools (navigate, back,
forward, reload, tabs, switch_tab, new_tab, close_tab, wait_for_duo),
page_tools (snapshot, find, wait_for, screenshot), pointer_tools (click,
click_at, drag, hover, scroll), action_tools (type_text, select_option,
press_key), dialog_tools (answer_dialog), and, only on a server with the
vault (the desktop one), file_tools (upload_file, read_download) and
credential_tools (list_credentials, fill_login).
"""

from mcp.server.mcpserver import MCPServer

from browser_tool.server.tool_runner import ToolRunner
from browser_tool.server.tools.action_tools import register_action_tools
from browser_tool.server.tools.credential_tools import register_credential_tools
from browser_tool.server.tools.dialog_tools import register_dialog_tools
from browser_tool.server.tools.file_tools import register_file_tools
from browser_tool.server.tools.navigation_tools import register_navigation_tools
from browser_tool.server.tools.page_tools import register_page_tools
from browser_tool.server.tools.pointer_tools import register_pointer_tools

__all__ = ["register_tools"]


def register_tools(
    server: MCPServer,
    runner: ToolRunner,
    *,
    has_vault: bool = True,
    allows_secret_fields: bool = False,
) -> None:
    """Register the browser tools on `server`.

    Args:
        server: The MCP server.
        runner: Runs every tool's action.
        has_vault: Also register list_credentials and fill_login, point
            type_text at fill_login, and register upload_file and read_download
            (the desktop server; the docker one has no vault, refuses uploads
            and saves no downloads).
        allows_secret_fields: [gates] allow_secret_fields is on: type_text's
            description says it types into password/OTP fields.
    """
    register_navigation_tools(server, runner)
    register_page_tools(server, runner)
    register_pointer_tools(server, runner)
    register_action_tools(
        server, runner, has_vault=has_vault, allows_secret_fields=allows_secret_fields
    )
    register_dialog_tools(server, runner)
    if has_vault:
        register_file_tools(server, runner)
        register_credential_tools(server, runner)

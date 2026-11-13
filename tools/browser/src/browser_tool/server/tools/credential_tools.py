"""The vault's MCP tools: list_credentials and fill_login (desktop server only).

Docstrings here are the descriptions the model reads.
"""

from mcp.server.mcpserver import MCPServer

from browser_tool import actions
from browser_tool.server.tool_runner import ToolRunner


def register_credential_tools(server: MCPServer, runner: ToolRunner) -> None:
    """Register list_credentials and fill_login on `server`."""
    tool = server.tool(structured_output=False)

    @tool
    async def list_credentials() -> str:
        """List saved logins (id, site, username hint). Secrets are never shown."""
        return await runner.run("list_credentials", actions.list_credentials)

    @tool
    async def fill_login(credential_id: str, submit: bool = False) -> str:
        """Fill the login form on the current page from the vault; returns only ok or a reason.

        The vault checks the site matches the credential. You never see the
        password. Set submit=true to also submit the form.
        """
        return await runner.run("fill_login", actions.fill_login, credential_id, submit)

"""The MCP tools that fill fields and press keys: type_text, select_option and press_key.

Docstrings here are the descriptions the model reads. type_text's description is
a constant instead, because a server without the vault (docker jobs) has no
fill_login to point at, and a server with [gates] allow_secret_fields (the job
runner) types into password/OTP fields.
"""

from mcp.server.mcpserver import MCPServer

from browser_tool import actions
from browser_tool.server.tool_runner import ToolRunner

_TYPE_TEXT_HOW = (
    " append=true adds to the end instead; slowly=true types key by key, for fields "
    "that react to each key. It never presses Enter: use press_key to submit."
)
TYPE_TEXT_DESCRIPTION = (
    "Replace the text in a field (by ref). Refuses password/OTP fields: use fill_login."
    + _TYPE_TEXT_HOW
)
TYPE_TEXT_NO_VAULT_DESCRIPTION = (
    "Replace the text in a field (by ref). Refuses password/OTP fields: this browser "
    "has no saved logins, and passwords or codes must never be typed." + _TYPE_TEXT_HOW
)
TYPE_TEXT_SECRET_FIELDS_DESCRIPTION = (
    "Replace the text in a field (by ref). Password/OTP fields are allowed here, only for "
    "dedicated accounts this browser's job runner creates; the owner's real logins use "
    "fill_login." + _TYPE_TEXT_HOW
)


def register_action_tools(
    server: MCPServer, runner: ToolRunner, *, has_vault: bool, allows_secret_fields: bool
) -> None:
    """Register type_text, select_option and press_key on `server`.

    Args:
        server: The MCP server.
        runner: Runs every tool's action.
        has_vault: Point type_text's description at fill_login.
        allows_secret_fields: [gates] allow_secret_fields is on, so type_text's
            description says it types into password/OTP fields.
    """
    tool = server.tool(structured_output=False)
    type_text_description = TYPE_TEXT_DESCRIPTION if has_vault else TYPE_TEXT_NO_VAULT_DESCRIPTION
    if allows_secret_fields:
        type_text_description = TYPE_TEXT_SECRET_FIELDS_DESCRIPTION

    @server.tool(structured_output=False, description=type_text_description)
    async def type_text(ref: str, text: str, append: bool = False, slowly: bool = False) -> str:
        return await runner.run("type_text", actions.type_text, ref, text, append, slowly)

    @tool
    async def select_option(ref: str, value: str | list[str]) -> str:
        """Choose an option (by value or visible label) in a dropdown with this ref.

        Pass a list to choose several in a multi-select.
        """
        return await runner.run("select_option", actions.select_option, ref, value)

    @tool
    async def press_key(key: str) -> str:
        """Press a key on the focused element, e.g. "Tab", "Escape", "Enter", "Control+A".

        Keys that buy, send or delete (e.g. Enter on a "Send" button or in a message
        box, or the Delete key) wait for the owner's approval; other keys run at
        once. Paste keys (Control+V, Shift+Insert) are refused. Use type_text to
        enter text.
        """
        return await runner.run("press_key", actions.press_key, key)

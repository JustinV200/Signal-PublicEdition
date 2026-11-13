# browser_tool.server.tools

The MCP tool list. Public API: `register_tools(server, runner, *, has_vault=True)`, used by `server.app`.

- `navigation_tools.py`: navigate, back, forward, reload, tabs, switch_tab, new_tab, close_tab, wait_for_duo.
- `page_tools.py`: snapshot, find, wait_for, screenshot.
- `pointer_tools.py`: click, click_at, drag, hover, scroll.
- `action_tools.py`: type_text, select_option, press_key. The `type_text` description depends on `has_vault`.
- `dialog_tools.py`: answer_dialog, and upload_file only when `has_vault` (the docker server, which has no vault, also refuses uploads).
- `credential_tools.py`: list_credentials, fill_login. These are registered only when `has_vault`.

Each tool is a thin typed wrapper whose docstring is the description the model reads. It hands off to `ToolRunner.run` with the matching `browser_tool.actions` function. Depends on `mcp`, `browser_tool.actions` and `server.tool_runner`.

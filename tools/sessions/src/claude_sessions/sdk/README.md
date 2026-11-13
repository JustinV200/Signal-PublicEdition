# sdk

The thin adapter over `claude-agent-sdk` 0.2.168. The daemon gets plain events and a client it can fake.

- `LaunchSpec`, `build_options(spec, can_use_tool)`: the `ClaudeAgentOptions` for a managed session.
  - Loads `setting_sources=["user","project","local"]` and the `claude_code` system-prompt preset. With `None`, the SDK would send an empty system prompt.
  - Passes flag settings that disable bypass mode, plus the validated permission mode.
  - The same flag settings carry `SECRET_DENY_RULES` (`secret_rules.py`) as `permissions.deny`. Flag settings outrank every settings file except managed settings, and deny rules merge from all sources anyway, so no settings file can lift them.
    - `Read` and `Edit` rules for `.env` files, `.state` and `.cache` folders and the browser's `.profile` and `.screenshots`, anchored at `//**/` so they hold in every repo on every drive.
    - `Read` and `Edit` rules for `~/.ssh`, Claude Code's credentials and IDE lock files, and the vault store (`~/AppData/Local/signal-vault`).
    - `PowerShell` rules for `Get-Content` and `Select-String` naming any of those.
    - There are no Bash rules. The `Read` and `Edit` rules already cover Bash reads and writes that name the file (`cat`, `head`, `tail`, `sed`, `tee`, `< file`, `> file`), and a rule matching command words couldn't catch a read that doesn't name it.
    - Flip side: the scoped `PowerShell` rules keep the PowerShell tool on in a repo whose settings deny a Bash command, so managed sessions there lose the CLI's automatic PowerShell shutoff. Their PowerShell calls still reach the dialog unless the CLI counts them as read-only. In `acceptEdits` mode, `Set-Content`, `Add-Content`, `Clear-Content` and `Remove-Item` (and their aliases) on paths inside the repo also run without a dialog.
    - Known gaps: the rules only stop reads that name the file. `grep -r TOKEN .` reads `.env` silently, `Get-ChildItem -Recurse | Select-String` probably does too, and 8.3 short names (`ENV~1`, `STATE~1`) may slip past.
    - The lists are a copy of audiohub's `brain/permissions/secret_paths.py`. Change both together.
  - Sets `SIGNAL_BRIEF_SURFACE=managed` in the CLI's environment, so Signal's brief hook and tools never count the session as the owner reading a brief.
  - Starts with either `session_id` (new session) or `resume` (existing one).
- `make_can_use_tool(decide)`: wraps a `ToolCall -> bool` decider as the SDK callback. A decider that raises denies the call.
- `translate_message(message)`: SDK messages become `AssistantText`, `SessionIdentified` and `TurnEnded`. Subagent text is dropped.
- `SessionClient`, `ClientFactory`, `create_sdk_client`: the client protocol, and the real `ClaudeSDKClient`.

Depends on: `approvals`, and `claude_agent_sdk`.

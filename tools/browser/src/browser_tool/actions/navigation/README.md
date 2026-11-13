# browser_tool.actions.navigation

Where the tab is and which tab is current. Public API: `navigate`, `back`, `forward`, `reload`, `list_tabs`, `switch_tab`, `new_tab`, `close_tab` (re-exported by `browser_tool.actions`), plus `NavigationWatch`, `settle_max_s` and `KEY_START_GRACE_S` for `actions.pointer`.

- `navigate.py`: `navigate(ctx, url)`, and `checked_target(ctx, url)`, the scheme, form and policy check (new_tab uses it too). It settles through a `NavigationWatch`, then reports through `signin.report_location`.
- `history.py`: `back(ctx)`, `forward(ctx)` and `reload(ctx)`, the same way. A step that would send a form's POST again is held back (`resubmit_guard.py`), then runs the send rule and only steps again on an Allow (or a log, when send isn't in `always_confirm`). `reload` refuses a Duo tab. A step that didn't move says "no previous page" or "no next page"; a hash-only step counts as a move.
- `load_failure.py`: `describe_load_failure`, shared by navigate and the history steps: a load that became a download, a blocked hop, or a plain failure.
- `resubmit_guard.py`: `ResubmitGuard`, which aborts the tab's main-frame POST navigations with ERR_ABORTED (the tab stays where it was) and notes them.
- `tabs.py`: `list_tabs(ctx)`, `switch_tab(ctx, index)`, `new_tab(ctx, url)` (policy-checked before it opens a tab, then loaded through `navigate`) and `close_tab(ctx, index)` (refuses the only tab).
- `nav_watch.py`: `NavigationWatch` records main-frame navigation requests and `framenavigated` during an action. It waits for the navigation to land only if one happened: commit, failure, download or a 204/205 answer, then load and a 0.25 s quiet spell. It is read only.

Depends on `actions` (context, errors, gating, guards, untrusted, signin), `policy` and `playwright`. Details are in `../README.md`.

# browser_tool.gates

Owner confirmation for sensitive actions such as buying, paying, sending, posting, deleting or transferring, and the rules that decide which of them ask and which only get logged. The owner answers in the shared `signal_confirm` Allow/Deny dialog (`packages/confirm`), and the model has no tool that can answer it. Known limit: the model's shell runs as the same Windows user, so a same-user process could in principle script the dialog (the same-user limit in `refdocs/research/password-vault.md`).

## Public API (`from browser_tool.gates import ...`)

- `Confirmer` (Protocol): `async confirm(request: ConfirmationRequest) -> bool`.
  - It returns True only for an explicit yes. A timeout counts as no.
  - This is the seam for plugging in an audiohub spoken yes/no later.
- `ConfirmationRequest(action, origin, reason, frame_origin=None, job=None)`. `job` is the docker job's label; the dialog's first line starts with it. The desktop browser leaves it None.
  - `origin` comes from the browser, not the page.
  - `action` contains page-supplied text such as a button name.
- `DialogConfirmer(timeout_s, show_dialog=signal_confirm.confirm_async)` asks in the signal_confirm dialog.
  - The dialog is topmost, "Deny" is the default button, and Allow has no keyboard shortcut and is briefly disabled when the dialog appears.
  - It runs in a child process (the event loop keeps going) and shows one dialog at a time.
  - It denies by itself after `timeout_s`. A dialog that fails to show also counts as no.
- `build_dialog_text(request)` builds the dialog body: the action, site, frame and reason.
- `ActionRules(patterns).find_match(texts) -> str | None` does case-insensitive regex matching.
- `ConfirmRules(category_patterns, always_confirm, extra_patterns=())` sorts sensitive actions into "ask" and "log".
  - It keeps one `ActionRules` per category. The categories and their patterns are `browser_tool.config.CATEGORY_PATTERNS`, `always_confirm` is `[gates] always_confirm`, and `extra_patterns` is `[gates] patterns`, which always ask.
  - `check(category, reason) -> GateCheck` asks only if `category` is in `always_confirm`. `None` is for rules that only log.
  - `check_texts(texts) -> GateCheck | None` matches every category. A match that asks wins over one that only logs.
- `GateCheck(reason, must_confirm, asking)` is a rule's verdict; `asking` is the set of categories that ask (not part of equality). `strictest(*checks)` returns the first that asks, else the first one, else None, with `asking` unioned over all of them.
- `key_kind(key)` is the press_key allowlist. It returns `KEY_FREE`, `KEY_MOVE` or `KEY_GATED`.
  - Tab, Shift+Tab and Escape are `KEY_FREE`.
  - The arrows, Home, End, PageUp and PageDown are `KEY_MOVE`. The caller treats them as free only when focus is not on a form control or ARIA widget, because these keys change the value of a select, radio or slider.
  - Every other valid key is `KEY_GATED` and goes through the gate rules (see `browser_tool.actions`).
  - It raises `ValueError` for control characters (such as a raw `"\r"`) and unknown key names.
- `key_name(key)` drops the modifiers and lowercases: `"Control+Enter"` is `"enter"`. `ENTER_KEYS`, `SPACE_KEYS` and `DELETE_KEY` are the names the rules look at.
- `is_send_shortcut(key)` is True for Enter held with Control or Meta, which sends in most mail and chat apps.

## Files

- `confirmer.py`: the protocol and the request type.
- `dialog_confirmer.py`: the signal_confirm adapter and the dialog text.
- `action_rules.py`: pattern matching.
- `confirm_rules.py`: the ask-or-log decision per category.
- `key_rules.py`: the press_key allowlist.

## Dependencies

`signal_confirm` (`packages/confirm`, stdlib only) for the dialog; otherwise the standard library (`asyncio`, `re`).

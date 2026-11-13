# browser_tool.actions.gating

The gate rules behind the pointer tools (`click`, `click_at`, `drag`, and the log-only `hover` and `scroll`), `type_text`, `select_option`, `press_key`, and a history step that would resubmit a form. They read the live page to decide whether an action is sensitive and in which `[gates] always_confirm` category, then ask the owner or log it. The rules themselves are listed in `../README.md` ("Gating and origin rules").

## Public API (`from browser_tool.actions.gating import ...`)

- `click_gate_check(ctx, target, label, frame_origin, *, scroll_first=True)`: the rule a click (or either end of a drag) falls under, or None. `target` is a locator or an element handle; `click_at` passes `scroll_first=False`, since its click point is fixed on screen.
- `log_only(check)`: the same check, downgraded so it only logs (hover and scroll).
- `select_texts(target, value)` and `gate_check(ctx, texts, frame_origin)`: a dropdown choice's live texts, and the text and unverified-frame rules on them.
- `focused_target(page)` returns a `FocusedTarget` (the focused element across frames); `key_gate_check(ctx, page, key, focus)` is the rule a key press on it falls under.
- `confirm_or_log(ctx, page, GatedAction(prompt, log_target, frame_origin), check)` asks the owner when the check must be confirmed and returns the origin they approved; otherwise it logs one INFO line and returns None. A decline, timeout or dialog failure raises `ActionError`.

## Files

- `confirmation.py`: the gate rules for clicks, selects and keys.
- `page_scripts.py`: the in-page scripts those rules read the target with (main world).
- `owner_prompt.py`: asking the owner, or logging an auto-allowed action.

## Dependencies

`playwright`, browser_tool `config`, `gates` and `policy`, and the parent package's `context`, `errors` and `snapshot` modules.

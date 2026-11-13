# browser_tool.actions.pointer

The tools that act on the page. Public API (re-exported by `browser_tool.actions`): `click`, `click_at`, `drag`, `hover`, `scroll`, `type_text`, `select_option`, `press_key`. Also exported for `answer_dialog` and `upload_file`: `prepare_ref`, `RefTarget`, `log_target` and `act_and_report`.

- `target.py`: `prepare_page` (current tab, Duo lockout, then origin check) and `prepare_ref` (also the ref, its label and its frame check), shared by every tool here.
- `clicks.py`: `click(ref, button, double, modifiers)`. Every variant goes through the same click rules.
- `click_at.py`: `click_at(x, y)`. Gates on the deepest element at the point, through shadow roots and iframes; a frame it can't see into counts as unverified. It refuses if another element is at the point right before the click.
- `drag.py`: `drag(source, target)`. Both ends go through the click rules and the strictest wins.
- `passive.py`: `hover(ref)` and `scroll(ref, direction, amount)`. Never ask, only log, but run the Duo, origin and frame checks.
- `fields.py`: `type_text(ref, text, append, slowly)` and `select_option(ref, value or values)`. type_text refuses secret fields and never presses Enter or Tab; select_option gates on every option.
- `keys.py`: `press_key`, an allowlist of keys. Paste keys are refused, and a key gets a short start grace for the navigation it may set off.
- `after_action.py`: `act_and_report`, the last-moment check, the action, the settle and the shared result (URL, closed or new tab, blocked navigations, signed-out note), for click, click_at, drag, press_key, answer_dialog and upload_file; and `act_checked`, the last-moment check plus the action in one task, which stops waiting when the action opens a page dialog (type_text, select_option, hover and scroll use it directly).

Every action refuses a Duo tab first and calls `guards.ensure_ready_to_act` right before it touches the page, with no await in between. Depends on `actions` (context, errors, gating, guards, navigation, signin, untrusted), `gates` and `redaction`. Details are in `../README.md`.

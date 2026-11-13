"""The field tools: type_text and select_option, by snapshot ref.

Each first refuses a tab showing a Duo prompt (owner-only), checks the page
origin and resolves the ref (target.prepare_ref). Both checks run again right
before the page is touched (guards.ensure_ready_to_act, through
after_action.act_checked, which also stops waiting if the page opens a
dialog), because an owner dialog can wait up to minutes and an approved
action must still be on the origin the owner approved.

type_text refuses password/OTP fields: those are filled by the vault only (the
refusal text is ctx.password_field_refusal, since a server without the vault
has no fill_login to point at), unless [gates] allow_secret_fields is on (the
job runner's dedicated accounts). Typed text is never logged, only its length,
and a value in a secret field stays redacted and scrubbed from every result.
It replaces the field's text, or with append=True adds to its end; slowly=True
types key by key (for fields that react to each key). It never presses Enter
or Tab, so typing can't submit a form or move focus to another field: other
control characters are inserted as text, and line breaks go in through the
DOM (a textarea's setRangeText, or insertLineBreak, the Shift+Enter edit, in
a contenteditable), never as a key or text input event, since Edge submits a
single-field form even on an inserted line break. A single-line input drops
them, as fill() does.

select_option gates on every option it picks (a multi-select choosing
"Archive" and "Delete" asks as a delete), plus the select's live name.
Page-supplied labels in results are wrapped as untrusted content.
"""

import logging
import re
from collections.abc import Sequence

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import GatedAction, confirm_or_log, gate_check, select_texts
from browser_tool.actions.pointer.after_action import DIALOG_OPENED_NOTE, act_checked
from browser_tool.actions.pointer.target import RefTarget, log_target, prepare_ref
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.redaction import is_sensitive_locator

logger = logging.getLogger(__name__)

MAX_TYPE_CHARS = 10_000
MAX_OPTIONS = 50
NOT_FOCUSED = "refused: could not put the cursor in that field; click it first"
# Control characters, which a key-by-key type could press as keys (Enter, Tab).
CONTROL_CHAR_RE = re.compile(r"([\x00-\x1f\x7f])")
LINE_BREAK = "\n"
# Insert one line break at the caret without a key or text input event; a
# single-line input can't hold one, so it is dropped there.
LINE_BREAK_JS = r"""(el) => {
  const field = el.tagName === 'LABEL' && el.control ? el.control : el;
  if (field.tagName === 'TEXTAREA') {
    field.setRangeText('\n', field.selectionStart, field.selectionEnd, 'end');
    field.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertLineBreak'}));
  } else if (field.isContentEditable) {
    document.execCommand('insertLineBreak');
  }
}"""
# The field a ref means (a <label> is followed to its control), and whether it has
# focus (through open shadow roots).
_FIELD_JS = "const field = el.tagName === 'LABEL' && el.control ? el.control : el;"
_RETURN_IS_FOCUSED_JS = """
  let focused = document.activeElement;
  while (focused && focused.shadowRoot && focused.shadowRoot.activeElement) {
    focused = focused.shadowRoot.activeElement;
  }
  return focused === field;"""
# Focus the field and put the caret at the end; returns whether it now has focus.
CARET_TO_END_JS = (
    "(el) => {"
    + _FIELD_JS
    + """
  field.focus();
  if (field.isContentEditable) {
    const range = document.createRange();
    range.selectNodeContents(field);
    range.collapse(false);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
  } else if (typeof field.setSelectionRange === 'function') {
    try { field.setSelectionRange(field.value.length, field.value.length); } catch (e) {}
  }"""
    + _RETURN_IS_FOCUSED_JS
    + "}"
)
# Whether the field still has focus (slowly checks before every key).
HAS_FOCUS_JS = "(el) => {" + _FIELD_JS + _RETURN_IS_FOCUSED_JS + "}"


async def type_text(
    ctx: ActionContext, ref: str, text: str, append: bool = False, slowly: bool = False
) -> str:
    """Type `text` into a text field: replace its content, or add to its end.

    Secret (password/OTP) fields are refused unless [gates] allow_secret_fields.

    Args:
        ctx: The action context.
        ref: The field's snapshot ref.
        text: What to type (at most MAX_TYPE_CHARS).
        append: Add to the end of the field's text instead of replacing it.
        slowly: Type key by key, for fields that react to each key press.

    Raises:
        ActionError: If the text is too long, the field is secret (and not allowed), can't be
            focused, or the checks refuse.
    """
    if len(text) > MAX_TYPE_CHARS:
        raise ActionError(f"text too long ({len(text)} chars; max {MAX_TYPE_CHARS})")
    target = await prepare_ref(ctx, ref)
    page = target.page
    is_allowed = ctx.settings.gates.allow_secret_fields
    if not is_allowed and await is_sensitive_locator(page, target.locator):
        raise ActionError(ctx.password_field_refusal)
    # Typing is checked only for its frame; what it types is never logged.
    action = GatedAction(
        f"type into {target.label}", log_target("type_text", ref, target.label), target.frame_origin
    )
    check = gate_check(ctx, [], target.frame_origin)
    approved_origin = await confirm_or_log(ctx, page, action, check)

    async def act() -> None:
        if not append and not slowly:
            await target.locator.fill(text)
        else:
            # Checked (act_checked) before the clear and the focus, which already
            # change the page.
            await _focus_end(target, clear=not append)
            await _type_at_caret(target, text, slowly)

    is_done = await act_checked(ctx, page, approved_origin, act, [target.label])
    logger.info("typed %d chars into %s", len(text), ref)
    verb = "added" if append else "typed"
    result = f"{verb} {len(text)} characters into {wrap_untrusted(target.label)}"
    return result if is_done else f"{result}; {DIALOG_OPENED_NOTE}"


async def _focus_end(target: RefTarget, *, clear: bool) -> None:
    """Focus the field with the caret at its end, after emptying it if `clear`.

    Raises:
        ActionError: If the field doesn't take focus (keys would go elsewhere).
    """
    if clear:
        await target.locator.fill("")
    if not await target.locator.evaluate(CARET_TO_END_JS):
        raise ActionError(NOT_FOCUSED)


async def _type_at_caret(target: RefTarget, text: str, slowly: bool) -> None:
    """Insert `text` at the caret, or with `slowly` type it key by key.

    Control characters are inserted as text and line breaks through the DOM,
    never pressed as keys (see the module docstring). With `slowly`, focus is
    checked before every key: a page that moves focus mid-typing (to a button,
    where a space would press it) stops the typing.

    Raises:
        ActionError: NOT_FOCUSED if the field lost focus while typing slowly.
    """
    keyboard = target.page.keyboard
    normalized = text.replace("\r\n", LINE_BREAK).replace("\r", LINE_BREAK)
    for piece in CONTROL_CHAR_RE.split(normalized):
        if piece == LINE_BREAK:
            await target.locator.evaluate(LINE_BREAK_JS)
        elif piece and not slowly:
            await keyboard.insert_text(piece)
        else:
            for char in piece:
                # Known leak: a page that moves focus on this key's own keydown
                # gets this one key in the new place (a space could press a
                # button); the check before the next key then stops the typing.
                if not await target.locator.evaluate(HAS_FOCUS_JS):
                    raise ActionError(NOT_FOCUSED)
                if CONTROL_CHAR_RE.fullmatch(char):
                    await keyboard.insert_text(char)
                else:
                    await keyboard.type(char)


async def select_option(ctx: ActionContext, ref: str, value: str | Sequence[str]) -> str:
    """Choose the option(s) whose value or visible label is `value` in a <select>.

    Args:
        ctx: The action context.
        ref: The dropdown's snapshot ref.
        value: One option, or a list of them for a multi-select.

    Raises:
        ActionError: If it isn't a <select>, an option is missing, or the owner declined.
    """
    values = [value] if isinstance(value, str) else list(value)
    if not 0 < len(values) <= MAX_OPTIONS:
        raise ActionError(f"give 1 to {MAX_OPTIONS} options")
    target = await prepare_ref(ctx, ref)
    # Gate on what the page will actually select and its live name, not on the
    # model's value codes or the snapshot label (a <label> ref reads "generic").
    found = [await select_texts(target.locator, one) for one in values]
    name = found[0][0]
    options = [option for _, option in found]
    texts = [target.label, name, *(text for option in options for text in option)]
    check = gate_check(ctx, texts, target.frame_origin)
    shown_name = name or target.label
    chosen = ", ".join(f"'{option[0]}'" for option in options)
    log = log_target("select_option", ref, target.label)
    action = GatedAction(f"select {chosen} in {shown_name}", log, target.frame_origin)
    approved_origin = await confirm_or_log(ctx, target.page, action, check)
    picked: list[str] = []

    async def act() -> None:
        picked.extend(await target.locator.select_option(values))

    trigger = [shown_name, *(option[0] for option in options)]
    if not await act_checked(ctx, target.page, approved_origin, act, trigger):
        return f"selecting in {wrap_untrusted(shown_name)}; {DIALOG_OPENED_NOTE}"
    selected = ", ".join(picked) or "nothing"
    return f"selected {wrap_untrusted(selected)} in {wrap_untrusted(shown_name)}"

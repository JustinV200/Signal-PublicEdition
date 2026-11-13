"""Find the login fields on a page. The vault picks fields itself; the model never gives selectors.

Rules: exactly one visible `input[type=password]` across all frames that
isn't autocomplete=`new-password` (Playwright's CSS engine also pierces open
shadow roots), so a login form next to a register form still works. Refused if
that field's form (or its root node, when it has no form) also holds a
`new-password` field: that's a change-password form, and filling it would put
the saved password in "current password". The username field is the one
marked autocomplete=username/email in the same form, else the last visible
text-like input before the password field.
"""

from dataclasses import dataclass

from vault.fill.page_protocol import ElementLike, PageLike

PASSWORD_SELECTOR = "input[type=password]"
NEW_PASSWORD_TOKEN = "new-password"

# Runs in the page against the password element; returns the username input or null.
USERNAME_FINDER_JS = """
(password) => {
  const textTypes = ['', 'text', 'email', 'tel'];
  const pool = password.form
    ? Array.from(password.form.elements)
    : Array.from(password.getRootNode().querySelectorAll('input'));
  const isVisible = (el) => (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null);
  const candidates = pool.filter((el) => el.tagName === 'INPUT'
    && textTypes.includes((el.getAttribute('type') || '').toLowerCase())
    && !el.disabled && isVisible(el));
  const autocompleteOf = (el) => el.getAttribute('autocomplete') || '';
  const hinted = candidates.find((el) => /\\b(username|email)\\b/i.test(autocompleteOf(el)));
  if (hinted) return hinted;
  const isBefore = (el) => el.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING;
  const before = candidates.filter(isBefore);
  return before.length ? before[before.length - 1] : null;
}
"""

# Runs in the page against the password element; true if its form (or root
# node) also has a new-password field, i.e. it's a change-password form.
SHARES_FORM_WITH_NEW_PASSWORD_JS = """
(password) => {
  const pool = password.form
    ? Array.from(password.form.elements)
    : Array.from(password.getRootNode().querySelectorAll('input'));
  return pool.some((el) => el.tagName === 'INPUT'
    && (el.getAttribute('type') || '').toLowerCase() === 'password'
    && /\\bnew-password\\b/i.test(el.getAttribute('autocomplete') || ''));
}
"""


@dataclass(frozen=True)
class LoginFields:
    """The handles the vault will fill. Both live in the same frame."""

    password: ElementLike
    username: ElementLike | None


async def _visible_password_inputs(page: PageLike) -> list[ElementLike]:
    """Return every visible password input in every frame of `page`."""
    visible: list[ElementLike] = []
    for frame in page.frames:
        for handle in await frame.query_selector_all(PASSWORD_SELECTOR):
            if await handle.is_visible():
                visible.append(handle)
    return visible


async def _is_new_password_field(handle: ElementLike) -> bool:
    autocomplete = await handle.get_attribute("autocomplete") or ""
    return NEW_PASSWORD_TOKEN in autocomplete.lower().split()


async def find_login_fields(page: PageLike) -> LoginFields | None:
    """Locate the password field (and the username field, if any) to fill.

    Args:
        page: The page to search.

    Returns:
        The fields, or None if there isn't exactly one visible password input
        that isn't a new-password field, or if that one shares its form with
        a new-password field (a change-password form).

    Raises:
        Exception: Playwright errors (e.g. a frame detached mid-search) propagate;
            the fill sequence turns them into a generic "error" result.
    """
    passwords = [
        handle
        for handle in await _visible_password_inputs(page)
        if not await _is_new_password_field(handle)
    ]
    if len(passwords) != 1:
        return None
    password = passwords[0]
    if await password.evaluate(SHARES_FORM_WITH_NEW_PASSWORD_JS):
        return None
    username = (await password.evaluate_handle(USERNAME_FINDER_JS)).as_element()
    return LoginFields(password=password, username=username)

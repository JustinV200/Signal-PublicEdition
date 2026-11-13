"""The in-page scripts the gate rules (gating/confirmation.py) read an action's target with.

They run in the page's main world, so they see the page's own DOM (shadow roots,
labels, forms). They read names, button-like values and <option> labels, never
field values (only a password field's value length, to tell a filled sign-in
from a decoy). Each returns plain JSON for confirmation.py to judge.
"""

# Longest text taken from one element, so a huge container can't flood the rules.
MAX_TEXT_CHARS = 500
# Visible text fields besides the password a sign-in form may have (user, code).
MAX_SIGN_IN_FIELDS = 2
# Below this drawn opacity a password field counts as a hidden decoy.
MIN_SHOWN_OPACITY = 0.1

# Shared helpers: accessible-ish text (input values only for button-type inputs),
# "is this a submit control", search forms and sign-in forms. A placeholder +
# replace, because f-strings would need every JS brace doubled.
_HELPERS_JS = """
const BUTTON_TYPES = ['submit', 'button', 'reset', 'image'];
const NON_TEXT_TYPES = [...BUTTON_TYPES, 'hidden', 'checkbox', 'radio', 'file', 'range', 'color'];
const textOf = (node) => [
  node.getAttribute('aria-label'), node.getAttribute('title'), node.getAttribute('alt'),
  node.innerText,
  node.tagName === 'INPUT' && BUTTON_TYPES.includes(node.type) ? node.value : null,
].filter(Boolean).join(' ').slice(0, MAX_TEXT_CHARS);
const isSubmit = (node) => (node.tagName === 'BUTTON' && node.type === 'submit')
  || (node.tagName === 'INPUT' && (node.type === 'submit' || node.type === 'image'));
const isTextInput = (node) => node.tagName === 'INPUT' && !NON_TEXT_TYPES.includes(node.type);
const SEARCH_LANDMARKS = 'search, [role~="search"]';
const SEARCH_BOXES = `${SEARCH_LANDMARKS}, [role~="searchbox"], input[type="search"]`;
// A combobox counts only as a form's single field, and only as an <input>:
// @-mention composers are comboboxes too, often textareas.
const SEARCH_FIELDS = `${SEARCH_BOXES}, input[name="q"], input[role~="combobox"]`;
// A search form is in a search landmark, or its only text field is a search field.
const isSearchForm = (form) => {
  if (form.closest(SEARCH_LANDMARKS)) return true;
  const fields = [...form.elements].filter((c) => isTextInput(c) || c.tagName === 'TEXTAREA');
  return fields.length === 1 && fields[0].matches(SEARCH_FIELDS);
};
// A submit that only loads a page: an explicit GET (Moodle's "Add submission" button).
// Only the attribute counts, because a form with no method is a GET too, and
// script-driven forms that send rarely set one.
const isGetSubmit = (form, submitter) =>
  ((submitter && submitter.getAttribute('formmethod')) || form.getAttribute('method') || '')
    .toLowerCase() === 'get';
// The element and its ancestors, across shadow hosts.
const selfAndAncestors = (node) => {
  const chain = [];
  for (let n = node; n instanceof Element; n = n.parentElement || n.getRootNode().host) {
    chain.push(n);
  }
  return chain;
};
// Product of the element's and its ancestors' opacity, as it is drawn.
const opacityOf = (node) => selfAndAncestors(node)
  .reduce((opacity, n) => opacity * Number(getComputedStyle(n).opacity), 1);
// Cut away by a clip-path or clip, or (for an ancestor) by a box of 1px or less
// that hides its overflow: the "visually hidden" wrapper and its cousins.
const isClippedBy = (n, isSelf) => {
  const style = getComputedStyle(n);
  if (style.clipPath !== 'none' || style.clip !== 'auto') return true;
  if (isSelf || (style.overflowX === 'visible' && style.overflowY === 'visible')) return false;
  const box = n.getBoundingClientRect();
  return box.width <= 1 || box.height <= 1;
};
// The field itself (or something inside it) is what's drawn at its centre, so no
// overlay covers it. Off the viewport this misses, which only makes it ask.
const isHitAtCentre = (node) => {
  const box = node.getBoundingClientRect();
  const hit = node.getRootNode().elementFromPoint(box.left + box.width / 2,
    box.top + box.height / 2);
  return Boolean(hit) && (hit === node || node.contains(hit));
};
// Really on screen: rendered, not hidden or nearly transparent, not a 0x0 decoy,
// inside the document rather than pushed off its edges, not clipped away and not
// covered.
const isShown = (node) => {
  const box = node.getBoundingClientRect();
  const page = node.ownerDocument.documentElement;
  const [left, top] = [box.left + scrollX, box.top + scrollY];
  const isOnPage = box.right + scrollX > 0 && box.bottom + scrollY > 0
    && left < page.scrollWidth && top < page.scrollHeight;
  return box.width > 1 && box.height > 1 && isOnPage
    && node.checkVisibility({opacityProperty: true, visibilityProperty: true})
    && opacityOf(node) >= MIN_SHOWN_OPACITY
    && !selfAndAncestors(node).some((n) => isClippedBy(n, n === node))
    && isHitAtCentre(node);
};
// A sign-in form: a visible password field that is filled (a decoy never is;
// fill_login fills the real one, with the vault's approval, right before the
// submit), no message or file fields, and at most MAX_SIGN_IN_FIELDS other
// rendered text fields. Only the value's length is read, never the value.
// Hidden password decoys and whole-page forms (ASP.NET wraps every page in one)
// don't count.
const isSignInForm = (form) => {
  const controls = [...form.elements];
  const isFilledPassword = (c) => c.type === 'password' && c.value.length > 0 && isShown(c);
  if (!controls.some(isFilledPassword)) return false;
  // A custom element may hold an editor in its shadow DOM: count it as one (fail-safe).
  const hasMessageField = controls.some((c) => c.tagName === 'TEXTAREA' || c.type === 'file')
    || Boolean(form.querySelector('[contenteditable]:not([contenteditable="false"])'))
    || [...form.querySelectorAll('*')].some((node) => node.tagName.includes('-'));
  // Counted when merely rendered (not the strict isShown), so hiding or scrolling
  // fields away can't make a long form look like a sign-in form.
  const otherFields = controls.filter((c) => isTextInput(c) && c.type !== 'password'
    && c.getClientRects().length > 0);
  return !hasMessageField && otherFields.length <= MAX_SIGN_IN_FIELDS;
};
// The submit rule's forms: not a search form, not an explicit GET. A sign-in form
// is reported separately; Python also checks the button's wording.
const isSendForm = (form, submitter) => !isSearchForm(form) && !isGetSubmit(form, submitter);
const deepFocus = (doc) => {
  let el = doc.activeElement;
  while (el && el.shadowRoot && el.shadowRoot.activeElement) el = el.shadowRoot.activeElement;
  return el;
};
const WIDGET_ROLES = ['listbox', 'combobox', 'radio', 'radiogroup', 'slider', 'spinbutton',
  'menu', 'menuitem', 'tab', 'tree', 'grid', 'switch', 'checkbox', 'option'];
const ROLE_SELECTORS = WIDGET_ROLES.map((role) => `[role~="${role}"]`);
"""
for _name, _value in {
    "MAX_TEXT_CHARS": MAX_TEXT_CHARS,
    "MAX_SIGN_IN_FIELDS": MAX_SIGN_IN_FIELDS,
    "MIN_SHOWN_OPACITY": MIN_SHOWN_OPACITY,
}.items():
    _HELPERS_JS = _HELPERS_JS.replace(_name, str(_value))

# Everything a click on `el` can trigger: the element hit at the centre of its box
# (where Playwright clicks) and every ancestor of it and of `el`, across shadow
# hosts, plus any <label>'s control. Returns their names, [text, is its own form a
# sign-in form] for the submit controls among them in send forms, and whether
# the click lands inside an <iframe>.
ELEMENT_INFO_JS = (
    "(el) => {"
    + _HELPERS_JS
    + """
  const INTERACTIVE = ['a', 'button', 'input', 'select', 'textarea', 'summary', 'label',
    '[onclick]', '[tabindex]', '[role~="button"]', '[role~="link"]', ...ROLE_SELECTORS].join(', ');
  const up = (node) => node.parentElement || node.getRootNode().host || null;
  const box = el.getBoundingClientRect();
  const [x, y] = [box.left + box.width / 2, box.top + box.height / 2];
  let hit = el.ownerDocument.elementFromPoint(x, y) || el;
  while (hit.shadowRoot) {
    const inner = hit.shadowRoot.elementFromPoint(x, y);
    if (!inner || inner === hit) break;
    hit = inner;
  }
  const chain = new Set();
  const climb = (start) => { for (let n = start; n; n = up(n)) chain.add(n); };
  climb(el);
  climb(hit);
  for (const node of [...chain]) if (node.tagName === 'LABEL' && node.control) climb(node.control);
  const isInteractive = (node) =>
    node.matches(INTERACTIVE) || getComputedStyle(node).cursor === 'pointer';
  const attrs = (node) => ['aria-label', 'title', 'alt'].map((name) => node.getAttribute(name));
  const namesOf = (node) => {
    const ids = (node.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean);
    const root = node.getRootNode();
    const names = [...attrs(node), ...ids.map((id) => (root.getElementById(id) || {}).textContent)];
    if (!isInteractive(node)) return names;
    // Icon buttons carry their name on an inner <img alt> or [aria-label].
    const inner = [...node.querySelectorAll('[alt], [aria-label]')].flatMap(attrs);
    return [...names, textOf(node), ...inner];
  };
  const nodes = [...chain];
  return {
    text: nodes.flatMap(namesOf).filter(Boolean).join(' '),
    submits: nodes.filter((node) => isSubmit(node) && node.form && isSendForm(node.form, node))
      .map((node) => [textOf(node), isSignInForm(node.form)]),
    landsInFrame: hit !== el && (hit.tagName === 'IFRAME' || hit.tagName === 'FRAME'),
  };
}"""
)

# The focused element (through open shadow roots), described for the key rules;
# null when nothing is focused in this frame. Keys are snake_case because they
# become FocusedTarget fields.
FOCUSED_TEXTS_JS = (
    "() => {"
    + _HELPERS_JS
    + """
  const WIDGETS = ['input, select, textarea, button', ...ROLE_SELECTORS].join(', ');
  const el = deepFocus(document);
  if (!el || el === document.body || el.tagName === 'IFRAME' || el.tagName === 'FRAME') return null;
  const controls = el.form ? [...el.form.elements].filter(isSubmit) : [];
  // What Enter would press: the focused submit control, or the form's default
  // button from any non-button input (Chromium presses it from a checkbox or radio too).
  const isFieldInput = el.tagName === 'INPUT' && !BUTTON_TYPES.includes(el.type);
  const submitter = isSubmit(el) ? el : isFieldInput ? controls[0] : null;
  // With no submit button, Enter in a form's only text input submits it anyway
  // (implicit submission).
  const isImplicitSubmit = Boolean(el.form) && isTextInput(el) && controls.length === 0
    && [...el.form.elements].filter(isTextInput).length === 1;
  const submitsForm = Boolean(el.form && (submitter || isImplicitSubmit))
    && isSendForm(el.form, submitter);
  const isSearch = Boolean(el.closest(SEARCH_BOXES) || (el.form && isSearchForm(el.form)));
  // A custom element without an open shadowRoot may hide a closed one we can't
  // see into: treat it as a control so value-changing keys are checked.
  const isOpaqueHost = el.tagName.includes('-') && !el.shadowRoot;
  return {
    texts: [textOf(el), ...controls.map(textOf)],
    is_control: el.isContentEditable || isOpaqueHost || Boolean(el.closest(WIDGETS)),
    is_submit: isSubmit(el),
    // An implicit submission has no button, so no text (and no save exception).
    submit_text: submitsForm ? (submitter ? textOf(submitter) : '') : null,
    in_sign_in_form: submitsForm && isSignInForm(el.form),
    is_search: isSearch,
    is_message_box: (el.isContentEditable || el.tagName === 'TEXTAREA') && !isSearch,
  };
}"""
)

# The select's live name and the label/value of the <option> select_option(value)
# would pick, after following a <label> to its control like Playwright does;
# null if there is no <select>.
OPTION_TEXTS_JS = r"""(el, wanted) => {
  const label = el.closest('label');
  const select = el.tagName === 'SELECT' ? el : label && label.control;
  if (!select || select.tagName !== 'SELECT') return null;
  const labelledBy = (select.getAttribute('aria-labelledby') || '').split(/\s+/)
    .map((id) => document.getElementById(id)).filter(Boolean);
  const name = [select.getAttribute('aria-label'), select.title,
    ...[...labelledBy, ...select.labels].map((node) => node.textContent)]
    .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  const option = [...select.options].find((o) => o.value === wanted || o.label === wanted);
  return {name, option: option ? [option.label, option.value] : []};
}"""

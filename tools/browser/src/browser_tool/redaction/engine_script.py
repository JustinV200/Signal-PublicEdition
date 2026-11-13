"""JavaScript for the "signal-sensitive" Playwright selector engine.

The engine matches password, one-time-code and similar secret inputs. It is the
single definition of "sensitive field" used by snapshot redaction, the type_text
refusal and screenshot masking. It is registered with content_script=True so it
runs in Playwright's isolated world, where page scripts can't patch the DOM APIs
it calls.

A field is sensitive when any of these hold:
- <input type=password>
- a text control whose autocomplete has current-password, new-password,
  one-time-code, cc-number or cc-csc
- a text control whose name/id/aria-label/placeholder/title/label text looks like
  a password, PIN, OTP/2FA/verification code or card security code
- a text control masked with CSS -webkit-text-security (fake password boxes)
"""

ENGINE_NAME = "signal-sensitive"

# Selector bodies: "any" matches every sensitive field; "focused" only the one that
# is its document's activeElement (works even when the window isn't focused).
SENSITIVE_SELECTOR = f"{ENGINE_NAME}=any"
FOCUSED_SENSITIVE_SELECTOR = f"{ENGINE_NAME}=focused"

ENGINE_SCRIPT = r"""
(() => {
  const SECRET_AUTOCOMPLETE = new Set([
    'current-password', 'new-password', 'one-time-code', 'cc-number', 'cc-csc',
  ]);
  // Long hints match anywhere; short tokens must start a word (avoid "spinner").
  const LONG_HINT = new RegExp([
    'pass(word|wd|code|phrase)', 'one[-_ ]?time', 'verif\\w*[-_ ]?code',
    'security[-_ ]?code', 'auth\\w*[-_ ]?code',
  ].join('|'), 'i');
  const SHORT_HINT = /(^|[^a-z0-9])(otp|totp|mfa|2fa|pin|cvv|cvc|csc|pwd)/i;
  const NON_TEXT_INPUTS = new Set([
    'button', 'submit', 'reset', 'image', 'checkbox', 'radio', 'file', 'range', 'color', 'hidden',
  ]);

  const isTextControl = (el) => {
    if (el.tagName === 'TEXTAREA') return true;
    if (el.tagName === 'INPUT') return !NON_TEXT_INPUTS.has(el.type);
    return el.isContentEditable === true;
  };

  const hintText = (el) => {
    const parts = ['name', 'id', 'aria-label', 'placeholder', 'title']
      .map((attribute) => el.getAttribute(attribute) || '');
    for (const label of el.labels || []) parts.push(label.textContent || '');
    return parts.join(' ');
  };

  const isSensitive = (el) => {
    if (el.nodeType !== 1) return false;
    if (el.tagName === 'INPUT' && el.type === 'password') return true;
    if (!isTextControl(el)) return false;
    const tokens = (el.getAttribute('autocomplete') || '').toLowerCase().split(/\s+/);
    if (tokens.some((token) => SECRET_AUTOCOMPLETE.has(token))) return true;
    const hints = hintText(el);
    if (LONG_HINT.test(hints) || SHORT_HINT.test(hints)) return true;
    const masking = getComputedStyle(el).webkitTextSecurity;
    return Boolean(masking) && masking !== 'none';
  };

  // Walks the root, its descendants and any open shadow roots below them.
  const collect = (root, found) => {
    if (root.nodeType === 1 && isSensitive(root)) found.push(root);
    for (const el of root.querySelectorAll('*')) {
      if (isSensitive(el)) found.push(el);
      if (el.shadowRoot) collect(el.shadowRoot, found);
    }
    return found;
  };

  const select = (root, selector) => {
    const found = collect(root, []);
    if (selector !== 'focused') return found;
    return found.filter((el) => el.getRootNode().activeElement === el);
  };

  return {
    query(root, selector) { return select(root, selector)[0] || null; },
    queryAll(root, selector) { return select(root, selector); },
  };
})()
"""

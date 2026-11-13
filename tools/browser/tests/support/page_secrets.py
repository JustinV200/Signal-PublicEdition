"""The secret values the fixture pages hold, for tests that prove none ever comes out."""

# fixtures/login.html: prefilled secret fields of every kind the redactor knows.
LOGIN_SECRETS = (
    "prefilled-pw-1234",  # type=password
    "654321",  # autocomplete=one-time-code
    "visible-new-pw-777",  # type=text, autocomplete=new-password
    "cvv-731",  # name=cvv
    "css-masked-555",  # -webkit-text-security
    "frame-pw-4242",  # password inside a srcdoc iframe
    "zero-size-pw-31",  # not interactable, so printed without a ref
    "no-pointer-pw-62",  # pointer-events:none, also printed without a ref
)

# fixtures/bypass.html: password values that leak into roles and other elements' names.
BYPASS_SECRETS = (
    "pw-as-button-1",  # password inputs exposed with other roles
    "pw-as-generic-2",
    "pw-as-slider-3",
    "pw-generic-inert-4",
    "named-secret-88",  # a button named via aria-labelledby from a password input
    "label-secret-99",  # a checkbox named by a label that contains a password input
    "mix: é",  # printed JSON-escaped (non-ASCII) inside a YAML-quoted key
)

# fixtures/mirror.html: a password value mirrored into page text and the title;
# the test then changes it to the second value (the title keeps the first).
MIRROR_SECRETS = ("mirror-secret-53", "changed-secret-17")
# Added to fixtures/mirror.html and pushed into the URL path: Edge percent-encodes
# the first; the others hold their own %XX, one valid and one not.
PATH_SECRETS = ("path secret ä-42", "Pa%55word-61", "ab%C3-73")

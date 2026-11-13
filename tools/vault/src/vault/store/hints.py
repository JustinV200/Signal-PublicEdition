"""Masked username hints, the only form of a username the model is shown."""

MASK = "***"


def username_hint(username: str) -> str:
    """Return a hint such as "j***@example.com" or "j***".

    Keeps the first character and, for email-style usernames, the domain.

    Args:
        username: The plaintext username.

    Returns:
        The hint ("" for an empty username).
    """
    if not username:
        return ""
    local, at, domain = username.rpartition("@")
    if at and local and domain:
        return f"{local[0]}{MASK}@{domain}"
    return f"{username[0]}{MASK}"

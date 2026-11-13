"""The token links to open the phone page with, as printed by `run --phone` and `phone-link`.

The local link works in a browser on this PC. The phone needs the HTTPS link
through Tailscale Serve, one per configured `[phone] allowed_hosts` name;
Serve answers on port 443, so that link has no port.
"""

from urllib.parse import urlencode

from audiohub.config import PhoneSettings

from .server import BIND_HOST, TOKEN_PARAM


def phone_link_lines(settings: PhoneSettings, token: str) -> list[str]:
    """Lines telling the owner which link to open where.

    Args:
        settings: The page port and the allowed Tailscale host names.
        token: The running server's token.

    Returns:
        One line for this PC, then one per Tailscale host (or a hint to set one).
    """
    query = urlencode({TOKEN_PARAM: token})
    lines = [f"on this PC: http://{BIND_HOST}:{settings.port}/?{query}"]
    lines += [f"on the phone: https://{host}/?{query}" for host in settings.allowed_hosts]
    if not settings.allowed_hosts:
        lines.append(
            "on the phone: first put this PC's Tailscale name in [phone] allowed_hosts "
            "(see tools/audiohub/PHONE.md)"
        )
    return lines

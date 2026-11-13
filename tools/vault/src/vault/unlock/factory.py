"""Picks the unlocker named by a vault's header. There is deliberately no fallback between them."""

from vault.unlock.base import PROVIDER_HELLO, PROVIDER_PASSPHRASE, Unlocker, UnlockError


def unlocker_for(provider: str) -> Unlocker:
    """Return the real unlocker for `provider`.

    A Hello vault never falls back to the passphrase path (or the reverse); if
    its unlocker fails, the fill fails.

    Args:
        provider: PROVIDER_HELLO or PROVIDER_PASSPHRASE, as recorded at `vault init`.

    Returns:
        A new unlocker.

    Raises:
        UnlockError: Unknown provider.
    """
    if provider == PROVIDER_HELLO:
        from vault.unlock.hello import HelloUnlocker

        return HelloUnlocker()
    if provider == PROVIDER_PASSPHRASE:
        from vault.unlock.passphrase import PassphraseUnlocker

        return PassphraseUnlocker()
    raise UnlockError(f"unknown unlock provider {provider!r}")

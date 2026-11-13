"""Build the ActionContext for the chosen backend (`browser-tool --backend local|docker`).

local (the default) is the desktop Edge profile with the vault, loaded lazily,
and owns the saved cookies (cookie_store: session cookies survive restarts).
docker runs each job in a throwaway container (refdocs/research/docker-browser.md):
the vault is never imported (MissingVaultFiller), the policy gets the container
block (the backend's guest block), and the password-field refusal and the
signed-out note don't point at fill_login, which that server doesn't register.
upload_file refuses there: sending the owner's files into a container job
waits on the owner's decision (README, Known gaps). read_download refuses
too, since that server saves no downloads. [gates] allow_secret_fields is
refused there: it is only for the job runner's desktop browser-jobs profile.
"""

from dataclasses import replace
from pathlib import Path

from browser_tool.actions import NO_VAULT_PASSWORD_REFUSAL, ActionContext
from browser_tool.backends import DockerBackend
from browser_tool.config import Settings
from browser_tool.cookie_store import CookieMode
from browser_tool.credentials import LazyVaultFiller, MissingVaultFiller
from browser_tool.gates import Confirmer

BACKEND_LOCAL = "local"
BACKEND_DOCKER = "docker"
BACKENDS = (BACKEND_LOCAL, BACKEND_DOCKER)
DOCKER_VAULT_OFF = "vault fills are off in docker jobs"
DOCKER_CONFIG_NAME = "tools/browser/browser-docker.toml"
DOCKER_SECRET_FIELDS_REFUSAL = "[gates] allow_secret_fields must be false for the docker backend"


def build_context(
    backend: str, settings: Settings, confirmer: Confirmer, config_path: Path | None = None
) -> ActionContext:
    """Wire the action context for `backend`.

    Args:
        backend: BACKEND_LOCAL or BACKEND_DOCKER.
        settings: The loaded settings.
        confirmer: Asks the owner about gated actions.
        config_path: The --config file, named in navigate's allowlist hint
            (default: the backend's usual file).

    Raises:
        ValueError: On an unknown backend, a malformed [policy] or [duo] pattern,
            or [gates] allow_secret_fields on for docker.
    """
    if backend == BACKEND_LOCAL:
        ctx = ActionContext.create(
            settings, confirmer, LazyVaultFiller(), cookie_mode=CookieMode.OWN
        )
        return replace(ctx, config_name=str(config_path)) if config_path else ctx
    if backend != BACKEND_DOCKER:
        raise ValueError(f"unknown backend {backend!r}; use one of {', '.join(BACKENDS)}")
    if settings.gates.allow_secret_fields:
        raise ValueError(DOCKER_SECRET_FIELDS_REFUSAL)
    ctx = ActionContext.create(
        settings, confirmer, MissingVaultFiller(DOCKER_VAULT_OFF), DockerBackend(settings)
    )
    return replace(
        ctx,
        password_field_refusal=NO_VAULT_PASSWORD_REFUSAL,
        has_vault=False,
        uploads_allowed=False,
        downloads_readable=False,
        config_name=str(config_path) if config_path else DOCKER_CONFIG_NAME,
    )

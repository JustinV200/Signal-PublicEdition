"""Everything an action needs, bundled so each tool function takes one argument.

ActionContext.create wires the real pieces from Settings; tests build it with a
fake Confirmer and a fake LoginFiller instead.
"""

import weakref
from dataclasses import dataclass, field

from playwright.async_api import Page

from browser_tool.actions.snapshot_cache import SnapshotCache
from browser_tool.backends import Backend
from browser_tool.config import CATEGORY_PATTERNS, Settings
from browser_tool.cookie_store import CookieMode
from browser_tool.credentials import LoginFiller
from browser_tool.gates import Confirmer, ConfirmRules
from browser_tool.policy import HostPolicy
from browser_tool.session import BrowserSession

# What type_text and press_key say in a password or one-time-code field.
PASSWORD_FIELD_REFUSAL = (
    "refused: this is a password or one-time-code field. Use fill_login(credential_id) "
    "instead; secrets must never pass through the model."
)
# The config file named in navigate's allowlist hint (the docker server reads its own).
DEFAULT_CONFIG_NAME = "tools/browser/browser.toml"
# The same, for a server with no credential tools (docker jobs have no vault).
NO_VAULT_PASSWORD_REFUSAL = (
    "refused: this is a password or one-time-code field. This browser has no saved "
    "logins: never type passwords or codes."
)


class RefLabels:
    """Per-page ref -> 'role "name"' labels from that page's latest snapshot.

    Used to describe a target in confirmation dialogs. Weak keys, so closed pages
    don't pile up.
    """

    def __init__(self) -> None:
        """Start with no labels."""
        self._by_page: weakref.WeakKeyDictionary[Page, dict[str, str]] = weakref.WeakKeyDictionary()

    def replace(self, page: Page, labels: dict[str, str]) -> None:
        """Store the labels of a new snapshot (older refs are invalid now)."""
        self._by_page[page] = labels

    def label_for(self, page: Page, ref: str) -> str:
        """The label for `ref`, or 'element <ref>' when unknown."""
        return self._by_page.get(page, {}).get(ref, f"element {ref}")


@dataclass
class ActionContext:
    """Shared state and collaborators for every MCP tool action."""

    settings: Settings
    policy: HostPolicy
    rules: ConfirmRules
    session: BrowserSession
    confirmer: Confirmer
    filler: LoginFiller
    ref_labels: RefLabels = field(default_factory=RefLabels)
    # Each tab's latest redacted snapshot, for snapshot paging, subtrees and find.
    snapshots: SnapshotCache = field(default_factory=SnapshotCache)
    # Each tab's secret field values as last read (secret_scrub); a tab frozen
    # by a dialog can't be read, so its scrub uses these.
    secret_values: weakref.WeakKeyDictionary[Page, set[str]] = field(
        default_factory=weakref.WeakKeyDictionary
    )
    password_field_refusal: str = PASSWORD_FIELD_REFUSAL
    # False for a server without the vault (docker jobs): the signed-out note
    # then doesn't point at fill_login.
    has_vault: bool = True
    # False for the docker server: upload_file refuses (owner decision pending).
    uploads_allowed: bool = True
    # False for the docker server: read_download refuses (its downloads are refused).
    downloads_readable: bool = True
    config_name: str = DEFAULT_CONFIG_NAME

    @classmethod
    def create(
        cls,
        settings: Settings,
        confirmer: Confirmer,
        filler: LoginFiller,
        backend: Backend | None = None,
        *,
        allow_relaunch: bool = True,
        holds_dialogs: bool = True,
        cookie_mode: CookieMode | None = None,
    ) -> "ActionContext":
        """Build the policy, the gate rules and an idle browser session from `settings`.

        The gate rules ask the owner only for [gates] always_confirm categories
        and the owner's own [gates] patterns.

        Args:
            settings: The tool's settings.
            confirmer: Asks the owner about gated actions.
            filler: The vault, or a stand-in that says why there is none.
            backend: Where Edge runs (default: the desktop profile). Its guest
                block, if any, goes into the policy.
            allow_relaunch: False for visit mode: once the browser closes, every
                later action fails with BrowserClosedError instead of relaunching.
            holds_dialogs: False for visit mode: page dialogs are dismissed
                instead of held for answer_dialog.
            cookie_mode: OWN for the desktop server, BORROW for visit mode,
                None to leave the saved cookies alone (docker jobs, tests).

        Raises:
            ValueError: If an allow/deny pattern or a [duo] code_relay_sites pattern is
                malformed.
        """
        policy = HostPolicy.from_strings(
            settings.policy.allow,
            settings.policy.deny,
            is_allow_all=settings.policy.allow_all,
            guest_block=backend.guest_block if backend is not None else None,
        )
        return cls(
            settings=settings,
            policy=policy,
            rules=ConfirmRules(
                CATEGORY_PATTERNS, settings.gates.always_confirm, settings.gates.patterns
            ),
            session=BrowserSession(
                settings,
                policy,
                backend,
                allow_relaunch=allow_relaunch,
                holds_dialogs=holds_dialogs,
                cookie_mode=cookie_mode,
            ),
            confirmer=confirmer,
            filler=filler,
        )

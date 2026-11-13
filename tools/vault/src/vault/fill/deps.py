"""`FillDeps`: everything the fill sequence talks to, injected so tests can swap each part."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vault.audit import AuditLog
from vault.confirm import Confirmer
from vault.fill.registry import FilledRegistry
from vault.unlock import Unlocker


@dataclass(frozen=True)
class FillDeps:
    """Collaborators of `fill_login_with`.

    Attributes:
        store_path: The vault's store.json.
        audit: Where fill outcomes are recorded.
        confirmer: Asks the owner to approve each fill.
        unlocker_for: Returns the unlocker for a vault's recorded provider.
        registry: Tracks filled fields for the snapshot gate and the scrubber.
    """

    store_path: Path
    audit: AuditLog
    confirmer: Confirmer
    unlocker_for: Callable[[str], Unlocker]
    registry: FilledRegistry

"""RunContext: what every agent option builder and security hook needs to know about a run."""

from dataclasses import dataclass
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.runs import Manifest


@dataclass
class RunContext:
    """One run's folder, manifest and chamber config.

    Attributes:
        run_dir: The run folder (private_root or analyses_root).
        manifest: The run's manifest; its `personal` flag drives the write hook.
        config: The chamber config (repo_root, models, paths).
    """

    run_dir: Path
    manifest: Manifest
    config: ChamberConfig

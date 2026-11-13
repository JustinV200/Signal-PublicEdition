"""Public API of browser_tool.backends: where Edge runs (the desktop, or a docker job)."""

from browser_tool.backends.docker_backend import IMAGE, DockerBackend
from browser_tool.backends.docker_box import (
    DOCKER_NOT_RUNNING,
    JobSpec,
    run_arguments,
    run_docker,
)
from browser_tool.backends.edge_version import REBUILD_COMMAND, compare_versions
from browser_tool.backends.host_addresses import HostAddresses, block_cidrs
from browser_tool.backends.local import LocalBackend, build_launch_options
from browser_tool.backends.profile_prefs import (
    DISABLED_SAVING_PREFS,
    disable_password_saving,
    merge_prefs,
)
from browser_tool.backends.types import Backend, BackendError

__all__ = [
    "DISABLED_SAVING_PREFS",
    "DOCKER_NOT_RUNNING",
    "IMAGE",
    "REBUILD_COMMAND",
    "Backend",
    "BackendError",
    "DockerBackend",
    "HostAddresses",
    "JobSpec",
    "LocalBackend",
    "block_cidrs",
    "build_launch_options",
    "compare_versions",
    "disable_password_saving",
    "merge_prefs",
    "run_arguments",
    "run_docker",
]

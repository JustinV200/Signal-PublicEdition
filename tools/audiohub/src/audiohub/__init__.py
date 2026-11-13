"""audiohub: the central audio tool for Claude in the Signal monorepo.

Subpackages (each with its own README.md):
  config  settings dataclasses, TOML loader, well-known paths
  audio   device lookup, microphone, speaker, resampling, music ducking
  cli     the `audiohub` command-line entry point

Run `uv run audiohub --help` from tools/audiohub for the command list.
"""

__version__ = "0.1.0"

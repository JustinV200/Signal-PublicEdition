"""Where the tool and the Signal repo live on disk, derived from this file's location.

The project is installed editable (uv's default for the project itself), so
__file__ is inside tools/analysis-chamber/src/analysis_chamber/config/.
"""

from pathlib import Path

# config/ -> analysis_chamber/ -> src/ -> analysis-chamber/
TOOL_DIR = Path(__file__).resolve().parents[3]
# analysis-chamber/ -> tools/ -> the Signal repo
REPO_ROOT = TOOL_DIR.parents[1]
DEFAULT_CONFIG_PATH = TOOL_DIR / "config.toml"

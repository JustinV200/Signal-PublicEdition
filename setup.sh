#!/bin/sh
# Signal setup (Linux, untested). Checks for uv, then runs the setup CLI in tools/setup.
# Windows-only tools are shown but can't be picked. The setup window is Windows-only, so a
# bare ./setup.sh runs the terminal setup. Usage: ./setup.sh [tool|tour|status|--no-ui]
set -e
if ! command -v uv >/dev/null 2>&1; then
    echo "Signal needs uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
cd "$(dirname "$0")"
exec uv run --project tools/setup --frozen --quiet setup "$@"

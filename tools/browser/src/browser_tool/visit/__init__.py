"""Public API of browser_tool.visit: visit mode, the `browser-tool-visit` command.

It visits a fixed plan of pages in one local Edge launch, through the same
ToolRunner the MCP server uses, with no model in the loop. See README.md.
"""

from browser_tool.visit.plan import MAX_TARGETS, PlanError, Target, parse_plan
from browser_tool.visit.result import PageResult, VisitResult, write_out
from browser_tool.visit.runner import run_visit

__all__ = [
    "MAX_TARGETS",
    "PageResult",
    "PlanError",
    "Target",
    "VisitResult",
    "parse_plan",
    "run_visit",
    "write_out",
]

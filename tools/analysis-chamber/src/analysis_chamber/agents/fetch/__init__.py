"""Fetching for the lead: polite downloads, page-to-text, run-folder storage, tool logic
and the Signal free-text swap hook. Raw content only ever goes to the extractor."""

from analysis_chamber.agents.fetch.download import Download, HttpDownloader
from analysis_chamber.agents.fetch.handlers import (
    WITHHELD,
    ChamberIO,
    ChamberTools,
    SourceSink,
    result,
)
from analysis_chamber.agents.fetch.http import FetchError, Response
from analysis_chamber.agents.fetch.ratelimit import SHARED_LIMITER, HostRateLimiter
from analysis_chamber.agents.fetch.signal_swap import (
    PASS_THROUGH_TOOLS,
    signal_failure_matcher,
    signal_swap_matcher,
)

__all__ = [
    "PASS_THROUGH_TOOLS",
    "SHARED_LIMITER",
    "WITHHELD",
    "ChamberIO",
    "ChamberTools",
    "Download",
    "FetchError",
    "HostRateLimiter",
    "HttpDownloader",
    "Response",
    "SourceSink",
    "result",
    "signal_failure_matcher",
    "signal_swap_matcher",
]

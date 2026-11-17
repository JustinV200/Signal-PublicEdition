"""The lead's in-process `chamber` MCP server: fetch, extract_file, search, get_api_key.

Thin SDK wrappers over fetch.ChamberTools and nested.SdkSignup; the logic and
its tests live there. Tool names as the lead sees them: mcp__chamber__<name>.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from analysis_chamber.agents.fetch import ChamberTools, result

SERVER_NAME = "chamber"
# Signup statuses that aren't errors for the lead.
OK_STATUSES = ("ok", "exists")
# (service, signup_url, env_var) -> {env_var, status, note}
Signup = Callable[[str, str, str], Awaitable[dict]]

_FETCH_DOC = (
    "Fetch a URL. A data file (CSV, JSON, XLSX, PDF, ...) is saved to data/raw and you get its "
    "path and first lines. A web page is read by a separate extractor and you get only its "
    "extract (also saved to extracts/). Failed sources come back as errors: skip and note them."
)
_EXTRACT_DOC = (
    "Run the extractor over a text file inside the run folder (e.g. free text saved under "
    "data/raw, or a PDF you converted to text) and get only the extract."
)
_FETCH_ARGS = {"url": str, "instructions": Annotated[str, "What to extract from it"]}
_SEARCH_DOC = "Search the web. Returns titles, URLs and dates only; read one with chamber_fetch."
_KEY_DOC = (
    "Get a FREE API key for a public data service via a signup agent. The key is saved to "
    "Signal's .env as env_var; you get only {env_var, status, note}, never the key."
)


def build_chamber_server(tools: ChamberTools, signup: Signup) -> McpSdkServerConfig:
    """The `chamber` server for one run.

    Args:
        tools: The run's fetch/extract/search logic.
        signup: The API-key signup (SdkSignup).

    Returns:
        The config to put in the lead's mcp_servers under SERVER_NAME.
    """

    @tool("chamber_fetch", _FETCH_DOC, _FETCH_ARGS)
    async def chamber_fetch(args: dict[str, Any]) -> dict[str, Any]:
        return await tools.fetch(str(args["url"]), str(args["instructions"]))

    @tool("chamber_extract_file", _EXTRACT_DOC, {"path": str, "instructions": str})
    async def chamber_extract_file(args: dict[str, Any]) -> dict[str, Any]:
        return await tools.extract_file(str(args["path"]), str(args["instructions"]))

    @tool("chamber_search", _SEARCH_DOC, {"query": str})
    async def chamber_search(args: dict[str, Any]) -> dict[str, Any]:
        return await tools.search(str(args["query"]))

    @tool("chamber_get_api_key", _KEY_DOC, {"service": str, "signup_url": str, "env_var": str})
    async def chamber_get_api_key(args: dict[str, Any]) -> dict[str, Any]:
        reply = await signup(str(args["service"]), str(args["signup_url"]), str(args["env_var"]))
        return result(json.dumps(reply), is_error=reply["status"] not in OK_STATUSES)

    return create_sdk_mcp_server(
        SERVER_NAME,
        tools=[chamber_fetch, chamber_extract_file, chamber_search, chamber_get_api_key],
    )

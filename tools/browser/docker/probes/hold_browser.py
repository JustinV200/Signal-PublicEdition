"""Connect to a container's Edge over CDP, print "connected", then wait to be killed.

Usage: SIGNAL_RELAY_TOKEN=<token> python hold_browser.py <port>
check_relay.check_idle_exit_after_kill starts this and kills it, the way
`taskkill /F` would end the MCP server, to show the relay notices the dropped
connections and ends the container. The token comes from the environment so
it never shows on a command line.
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

HOLD_S = 600
TOKEN_VARIABLE = "SIGNAL_RELAY_TOKEN"


async def hold(port: str, token: str) -> None:
    """Connect with the token header and sleep while connected."""
    async with async_playwright() as playwright:
        await playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {token}"}
        )
        print("connected", flush=True)
        await asyncio.sleep(HOLD_S)


if __name__ == "__main__":
    asyncio.run(hold(sys.argv[1], os.environ[TOKEN_VARIABLE]))

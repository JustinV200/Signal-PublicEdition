"""Runs INSIDE a container (fed to `python3 -I -` on stdin): try TCP connects, print JSON.

Usage: python3 -I - host:port [host:port ...]
For each target it resolves the name (IPv4), opens a TCP connection and closes
it at once without sending anything, and prints one JSON line:
{"target": ..., "address": ..., "result": "connected" | "refused" | "timeout" | "<error>"}.
Stdlib only, because the guest image has nothing else.
"""

import json
import socket
import sys

CONNECT_TIMEOUT_S = 3.0


def try_connect(target: str) -> dict[str, str]:
    """Resolve and connect to one host:port, returning what happened."""
    host, _, port = target.rpartition(":")
    try:
        address = socket.getaddrinfo(host, int(port), socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    except OSError as error:
        return {"target": target, "address": "", "result": f"dns: {error}"}
    try:
        with socket.create_connection((address, int(port)), timeout=CONNECT_TIMEOUT_S):
            result = "connected"
    except ConnectionRefusedError:
        result = "refused"
    except TimeoutError:
        result = "timeout"
    except OSError as error:
        result = f"error: {error}"
    return {"target": target, "address": address, "result": result}


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        print(json.dumps(try_connect(argument)), flush=True)

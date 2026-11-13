"""A stand-in for tools/setup's CLI in the console's tests (run as a real child process).

Prints `args <json list>`, then `stdin <text>` when stdin isn't empty, then exits with the
code a `--value=exit=N` argument names (0 otherwise).
"""

import json
import sys

args = sys.argv[1:]
print("args " + json.dumps(args))
text = sys.stdin.read() if not sys.stdin.isatty() else ""
if text:
    print("stdin " + text)
codes = [a.removeprefix("--value=exit=") for a in args if a.startswith("--value=exit=")]
sys.exit(int(codes[0]) if codes else 0)

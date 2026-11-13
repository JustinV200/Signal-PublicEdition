"""Child-process entry point: `python -I -m signal_confirm`, started by launcher.py.

Reads one DialogRequest as JSON on stdin, shows the dialog and prints "allow" or
"deny". Any error prints a traceback to stderr and exits non-zero, which the
parent treats as deny.
"""

import sys
import traceback

from signal_confirm.protocol import ALLOW_TOKEN, DENY_TOKEN, DialogRequest

ERROR_EXIT_CODE = 2


def main() -> int:
    """Run one dialog.

    Returns:
        The exit code: 0 with the answer on stdout, or ERROR_EXIT_CODE on any error.
    """
    try:
        request = DialogRequest.from_json(sys.stdin.buffer.read())
        # Imported here: a missing tkinter is caught below, and a bad request fails before Tk loads.
        from signal_confirm.dialog import show_dialog

        is_allowed = show_dialog(request)
    except Exception:
        traceback.print_exc()
        print(DENY_TOKEN)
        return ERROR_EXIT_CODE
    print(ALLOW_TOKEN if is_allowed else DENY_TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main())

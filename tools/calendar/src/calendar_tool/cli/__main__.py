"""`python -m calendar_tool.cli`: same as the `calendar` script.

The scheduled task runs it this way under pythonw, so no console window opens.
"""

import sys

from calendar_tool.cli.main import main

sys.exit(main())

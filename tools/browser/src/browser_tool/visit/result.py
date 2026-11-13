"""What one visit launch produced, and the out file the checker reads.

The out file is `{"status": "ok"|"busy"|"error", "pages": [{key, status, url, text}]}`.
A page's text is only what ToolRunner.run returned (already scrubbed and wrapped as
untrusted page content); its url is the target's display_url (no query string).
"""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# The launch's status.
STATUS_OK = "ok"
STATUS_BUSY = "busy"
STATUS_ERROR = "error"

# A page's status.
PAGE_OK = "ok"
PAGE_ERROR = "error"
PAGE_LOGIN_NEEDED = "login_needed"
PAGE_GOOGLE_SIGNIN_NEEDED = "google_signin_needed"


@dataclass(frozen=True)
class PageResult:
    """One target's outcome. text is "" unless status is PAGE_OK."""

    key: str
    status: str
    url: str
    text: str = ""


@dataclass(frozen=True)
class VisitResult:
    """The whole launch: its status, and one PageResult per target it got to."""

    status: str
    pages: tuple[PageResult, ...] = ()


def write_out(path: Path, result: VisitResult) -> None:
    """Write result as JSON to path, through a temp file so a reader never sees half of it.

    Raises:
        OSError: If the file can't be written.
    """
    data = {"status": result.status, "pages": [asdict(page) for page in result.pages]}
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, path)

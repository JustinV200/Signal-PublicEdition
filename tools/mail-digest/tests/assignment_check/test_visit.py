"""assignment_check.visit: only a fresh, well-formed out file from this launch is believed."""

import json
from pathlib import Path

import pytest

from mail_digest.assignment_check.check_config import load_check_config
from mail_digest.assignment_check.courses import CLASSROOM, site_pages
from mail_digest.assignment_check.visit import launch_paths, visit_site

PAGES = site_pages(CLASSROOM, load_check_config(Path(__file__).with_name("check_config.toml")))
GOOD = {"status": "ok", "pages": [{"key": PAGES[0].key, "status": "ok", "url": "u", "text": "t"}]}


@pytest.mark.parametrize(
    ("written", "status", "keys"),
    [
        (GOOD, "ok", [PAGES[0].key]),
        # The launch was killed and wrote nothing: the old file must not be read.
        (None, "error", []),
        (
            {"status": "ok", "pages": [{"key": "other-page", "status": "ok", "text": "t"}]},
            "error",
            [],
        ),
        ({"status": "done", "pages": []}, "error", []),
        ("not json", "error", []),
    ],
    ids=["fresh", "killed", "unknown-key", "bad-status", "not-json"],
)
def test_only_this_launchs_well_formed_out_file_counts(tmp_path, written, status, keys):
    _plan, out = launch_paths(CLASSROOM, tmp_path)
    out.write_text(json.dumps(GOOD), encoding="utf-8")  # a stale file from an earlier run

    def launch(argv):
        assert argv[argv.index("--out") + 1] == str(out)
        if written is not None:
            text = written if isinstance(written, str) else json.dumps(written)
            out.write_text(text, encoding="utf-8")

    visit = visit_site(CLASSROOM, PAGES, launch, tmp_path)
    assert (visit.status, [page.key for page in visit.pages]) == (status, keys)

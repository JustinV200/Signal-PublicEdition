"""Static serving: only files inside web/dist are served; traversal forms get index.html."""

import pytest

INDEX = b"<!doctype html><title>console</title>"
APP_JS = b"console.log('app');"


@pytest.mark.parametrize(
    ("target", "served"),
    [
        ("/assets/app.js", APP_JS),
        ("/some/client/route", INDEX),
        ("/../secret.txt", INDEX),
        ("/%2e%2e/secret.txt", INDEX),
        ("/assets/..%2f..%2fsecret.txt", INDEX),
        ("/..%5csecret.txt", INDEX),
        ("/assets\\..\\..\\secret.txt", INDEX),
        ("/{secret_path}", INDEX),  # an absolute drive path
        ("//{secret_path}", INDEX),
        ("/index.html%00", INDEX),  # NUL used to reach resolve() and crash it
    ],
)
async def test_only_files_inside_dist_are_served(console, target, served):
    dist = console.state_dir / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_bytes(INDEX)
    (dist / "assets" / "app.js").write_bytes(APP_JS)
    secret = console.state_dir / "secret.txt"
    secret.write_bytes(b"outside dist")

    status, body = await console.raw_request("GET", target.format(secret_path=secret.as_posix()))

    assert (status, body) == (200, served)

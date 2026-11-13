"""The docker run line: the relay is published on the host's loopback only, nothing is mounted."""

from pathlib import Path

from browser_tool.backends import IMAGE, JobSpec, run_arguments

PUBLISH_FLAGS = ("-p", "--publish")
FORBIDDEN_PREFIXES = ("-v", "--volume", "--mount", "--privileged", "-P", "--publish-all")


def test_run_line_publishes_on_loopback_only_and_mounts_nothing():
    spec = JobSpec("1a2b3c", "token-that-must-stay-off-argv", "10.0.0.0/8", "MAP x ~NOTFOUND")
    arguments = run_arguments(spec, IMAGE, Path("C:/seccomp.json"))
    published = [arguments[i + 1] for i, arg in enumerate(arguments) if arg in PUBLISH_FLAGS]
    assert published == ["127.0.0.1::9333"]
    assert not [arg for arg in arguments if arg.startswith(FORBIDDEN_PREFIXES)]
    assert "--network" not in arguments
    # The token reaches the container through docker's environment, never argv.
    assert not [arg for arg in arguments if spec.token in arg]

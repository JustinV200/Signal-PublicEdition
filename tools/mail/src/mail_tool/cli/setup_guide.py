"""`mail setup`: print the Google Cloud steps, then check the OAuth client file if it's there.

The full click-path is SETUP.md; this is the short version plus a validity
check that never prints the client secret.
"""

from mail_tool.auth import load_client_config
from mail_tool.config import CLIENT_SECRETS_PATH, TOOL_ROOT
from mail_tool.errors import SetupError

EXIT_OK = 0
EXIT_BAD_CLIENT = 2

STEPS = """\
Mail tool setup. The full click-path is {setup_doc}

1. https://console.cloud.google.com : create a project, then enable the Gmail API
   (APIs & Services > Library > Gmail API > Enable).
2. Google Auth Platform (the OAuth consent screen): Audience = External, add your
   addresses as test users, then Publish app (In production) so sign-ins don't
   expire after 7 days.
3. Google Auth Platform > Clients > Create client > Desktop app. Download the JSON
   right away and save it as:
   {client_path}
4. Sign in each account (a browser opens; Google warns the app is unverified:
   Advanced > Go to ... ):
   uv run --project tools/mail mail add personal --email you@example.com
"""


def run_setup() -> int:
    """Print the steps and the client file's status.

    Returns:
        0 when the file is missing (not done yet) or valid; 2 when it's present but invalid.
    """
    print(STEPS.format(setup_doc=TOOL_ROOT / "SETUP.md", client_path=CLIENT_SECRETS_PATH))
    if not CLIENT_SECRETS_PATH.is_file():
        print(f"OAuth client file: not there yet ({CLIENT_SECRETS_PATH}).")
        return EXIT_OK
    try:
        client = load_client_config(CLIENT_SECRETS_PATH)
    except SetupError as error:
        print(f"OAuth client file: PROBLEM. {error}")
        return EXIT_BAD_CLIENT
    project = client.project_id or "unknown project"
    print(f"OAuth client file: OK (Desktop app client, project {project}). Next: step 4.")
    return EXIT_OK

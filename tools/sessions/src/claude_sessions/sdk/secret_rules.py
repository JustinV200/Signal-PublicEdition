"""SECRET_DENY_RULES: CLI deny rules that keep managed sessions away from the owner's secrets.

build_options (options.py) passes them in the flag settings, which outrank
every settings file except managed settings. Deny rules merge from all
sources anyway, and a "!" carve-out only reaches rules from its own source,
so no repo's settings can drop them. They're a layer in front of the owner's
approval dialog, which never sees most reads: the CLI runs reads inside the
repo, and read-only commands such as cat, without asking. The rules stop the
reads that name a secret file; see the known gaps at POWERSHELL_READERS.

The lists are a copy of audiohub's (tools/audiohub/src/audiohub/brain/
permissions/secret_paths.py), which keep voice off the same files, with one
difference on purpose: audiohub also hides ~/.claude/projects (session
transcripts), which managed sessions need for their auto-memory. Audiohub's
rules are relative to its cwd, the Signal repo. A managed session can run in
any repo under C:\\src, so these anchor at "//" instead: the root of every
drive, as the CLI turns C:\\src into /c/src before matching.

TODO: move both copies into one package under packages/. Both tools' venvs
were running when this was written, and a new dependency needs a re-sync.
"""

from pathlib import PurePosixPath

# Names (gitignore patterns) of secret files at any depth.
SECRET_NAME_PATTERNS = (".env", ".env.*", "*.env")
# Folders whose contents are secret at any depth. In Signal, .state holds the
# mail tool's DPAPI sign-ins and google_client.json, and the whiteboard,
# console and sessions tokens; tools/audiohub/.cache holds the hub's IPC and
# Spotify tokens.
SECRET_DIRS = (".state", ".cache")
# Signal folders whose contents are secret: the browser profile, and
# screenshots of the owner's pages.
SECRET_PROJECT_DIRS = ("tools/browser/.profile", "tools/browser/.screenshots")
# Files and folders, relative to the home folder, holding credentials: SSH keys,
# Claude Code's login tokens, its IDE lock files (each holds an auth token),
# tools/vault's store (%LOCALAPPDATA%\signal-vault), git, GitHub CLI, AWS, npm,
# Docker, Kubernetes, Azure and gcloud credentials, and the owner's real browser
# profiles (Edge, Chrome, Firefox, Brave). Unlike audiohub's copy, this list
# leaves out ~/.claude/projects on purpose: a Read and Edit deny there would
# block managed sessions' own auto-memory (~/.claude/projects/<repo>/memory/).
# shortcut: the vault entry assumes LOCALAPPDATA is the default ~/AppData/Local;
# derive it from the variable if a profile ever moves it.
SECRET_HOME_PATHS = (
    ".ssh",
    ".claude/.credentials.json",
    ".claude/ide",
    "AppData/Local/signal-vault",
    ".git-credentials",
    ".config/gh",
    "AppData/Roaming/GitHub CLI",
    ".aws",
    ".npmrc",
    ".docker/config.json",
    "AppData/Local/Microsoft/Edge/User Data",
    "AppData/Local/Google/Chrome/User Data",
    "AppData/Roaming/Mozilla/Firefox/Profiles",
    "AppData/Local/BraveSoftware",
    ".kube",
    ".azure",
    "AppData/Roaming/gcloud",
    ".config/gcloud",
)

# "//**/" matches at any depth on every drive.
ANYWHERE = "//**/"

# Every list as gitignore patterns the Read and Edit rules take.
SECRET_PATH_PATTERNS = (
    *(f"{ANYWHERE}{pattern}" for pattern in SECRET_NAME_PATTERNS),
    *(f"{ANYWHERE}{folder}/**" for folder in (*SECRET_DIRS, *SECRET_PROJECT_DIRS)),
    # A home entry may be a file or a folder, so each gets both patterns.
    *(pattern for path in SECRET_HOME_PATHS for pattern in (f"~/{path}", f"~/{path}/**")),
)

# Read rules cover Grep, Glob and the Bash file commands the CLI recognises
# (cat, head, tail, sed ...). Edit rules cover every write tool, NotebookEdit
# among them, which a Read rule doesn't block.
FILE_RULE_TOOLS = ("Read", "Edit")

# PowerShell readers denied when their command names a secret. The CLI
# matches their aliases too (gc, cat and type for Get-Content, sls for
# Select-String). There are no Bash rules: the Read and Edit rules already
# cover Bash reads and writes that name the file (cat, head, tail, sed, tee,
# "< file", "> file"), and a rule matching command words couldn't catch a
# read that doesn't name it.
# Flip side: a scoped PowerShell deny rule keeps the PowerShell tool on in a
# repo whose settings deny a Bash command, so managed sessions there lose the
# CLI's automatic PowerShell shutoff. Their PowerShell calls still reach the
# approval dialog unless the CLI counts them as read-only, or, in acceptEdits
# mode, they're Set-Content, Add-Content, Clear-Content or Remove-Item (or an
# alias of one) on paths inside the repo, which run unapproved.
# shortcut: reads that don't name the file slip past every rule here:
# "grep -r TOKEN ." reads .env silently, "Get-ChildItem -Recurse |
# Select-String" probably does too, and so may 8.3 short names (ENV~1,
# STATE~1), other spellings ([IO.File]::ReadAllText, a script) and names built
# at run time. Add a PreToolUse check like audiohub's gate, or the CLI's
# sandbox, if these rules aren't enough.
POWERSHELL_READERS = ("Get-Content", "Select-String")


def _leaf_name(entry: str) -> str:
    """An entry's last part without wildcards: "*.env" -> ".env", ".claude/ide" -> "ide"."""
    return PurePosixPath(entry).name.strip("*").rstrip(".")


# Every list's names as a command would spell them (".env", ".state", ".ssh"
# ...), each once. Only dot-names count, as in audiohub: "ide" would match
# ordinary words.
_ALL_ENTRIES = (*SECRET_NAME_PATTERNS, *SECRET_DIRS, *SECRET_PROJECT_DIRS, *SECRET_HOME_PATHS)
SECRET_COMMAND_WORDS = tuple(
    dict.fromkeys(name for name in map(_leaf_name, _ALL_ENTRIES) if name.startswith("."))
)

SECRET_DENY_RULES = (
    *(f"{tool}({pattern})" for pattern in SECRET_PATH_PATTERNS for tool in FILE_RULE_TOOLS),
    *(
        f"PowerShell({reader} *{word}*)"
        for reader in POWERSHELL_READERS
        for word in SECRET_COMMAND_WORDS
    ),
)

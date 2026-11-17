"""Shell verbs and code calls that write or print files, shared by the path hooks.

personal_write_hook looks for WRITE_MARKERS and shell redirects into the repo,
raw_read_hook for PRINT_VERBS naming data/raw/signal, and env_file_hook for any of
them naming .env.
"""

import re

# Shell verbs (PowerShell, cmd, POSIX) and code calls that write, move or delete files.
# `>` isn't here: it's a comparison in Python, so shell redirects are checked by target
# (SHELL_REDIRECT) instead.
WRITE_MARKERS = re.compile(
    # Shell verbs, but not as a file suffix, flag or method (`a.md`, `-rm`, `df.copy()`).
    r"(?<![\w.\\/-])(?:Set-Content|Add-Content|Out-File|New-Item|Copy-Item|Move-Item"
    r"|Remove-Item|Rename-Item|Tee-Object|Export-Csv|Expand-Archive|Compress-Archive|sc|ac"
    r"|ni|cpi|mi|ri|del|erase|copy|move|ren|mkdir|md|rmdir|rd|cp|mv|rm|touch|tee|sed\s+-i"
    r"|robocopy|xcopy|git\s+(?:-C\s+(?:\S+\s+)?)?(?:add|commit|checkout|reset|restore|apply"
    r"|mv|rm|stash|clean|merge|rebase|pull))\b"
    # Code calls, incl. .NET's [IO.File]::WriteAllText; open() with a w, a or x mode.
    r"|\b(?:write_text|write_bytes|to_csv|to_parquet|to_excel|to_json|savefig|shutil"
    r"|os\.remove|os\.rename|os\.makedirs|unlink|json\.dump"
    r"|WriteAll(?:Text|Lines|Bytes)|AppendAll(?:Text|Lines))\b"
    r"|\bopen\s*\([^)]*['\"][wax][+bt]?['\"]",
    re.IGNORECASE,
)

# A shell redirect (`>`, `>>`, `2>`) and its target; not `->`, `=>` or `2>&1`.
SHELL_REDIRECT = re.compile(r"(?<![-=>])\d?>>?(?!&)\s*(\"[^\"]*\"|'[^']*'|[^\s;|&<>]+)")

# Shell verbs that print or search a file's text.
PRINT_VERBS = re.compile(
    r"\b(cat|type|Get-Content|gc|head|tail|more|less|Select-String|sls|findstr|grep|rg"
    r"|strings|Import-Csv|Format-Hex|od|xxd|awk|sed|jq|(?:python3?|py)\s+-m\s+json\.tool)\b",
    re.IGNORECASE,
)

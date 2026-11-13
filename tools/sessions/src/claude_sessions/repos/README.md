# repos

Finds the owner's local repos and their existing Claude Code sessions.

- `find_repos(roots, max_depth, claude_projects_dir=None)`: returns `Repo(name, path, is_git)`.
  - Finds git repos up to `max_depth` below each root. It skips `node_modules`, `.venv`, caches and build output, and never follows links or junctions.
  - Also returns folders under the roots where Claude Code has already run, read from the `cwd` in `~/.claude/projects` transcripts. Many of the owner's project folders (e.g. `C:\src\OtherRepo`) aren't git repos themselves.
- `resolve_repo(repo, repos, roots)`, `locate_repo(repo, roots, max_depth)`: turn a path or name into one folder inside the roots.
  - Name matching tries an exact case-sensitive name, then an exact name ignoring case, then a unique substring.
  - Raises `RepoNotFoundError` when nothing matches or several repos do.
- `require_inside_roots(path, roots)`: the containment check behind every session folder.
  - Refuses UNC and device paths (`\\host\share`, `\\?\`, `\\.\`, and mixed forms like `/\host\share`) from the text alone, using `PureWindowsPath(...).drive`. Even resolving such a path opens an SMB connection.
  - Resolves with `strict=True`, following links and junctions.
  - Requires the result to be inside a resolved root; otherwise raises `RepoOutsideRootsError`.
- `list_transcripts(repo_path=None, limit=20)`: returns `TranscriptSummary` (session id, last modified, truncated first prompt, title, cwd), newest first. It wraps the SDK's `list_sessions`.
- `find_transcript_cwd(session_id)`: the folder a session ran in, used to resume it.

Depends on: `text`, and `claude_agent_sdk` (`list_sessions`, `get_session_info`, which honour `CLAUDE_CONFIG_DIR`).

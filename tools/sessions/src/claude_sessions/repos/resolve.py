"""Turns what a person or model typed for "repo" into one repo folder inside the repo roots.

Accepted forms, in order: an existing folder path; an exact repo name (first
case-sensitive, then ignoring case); a substring that matches exactly one repo
name. Anything ambiguous fails with the candidates listed, so the caller can
ask again with a path. Every result passes require_inside_roots.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path

from claude_sessions.repos.containment import RepoNotFoundError, require_inside_roots
from claude_sessions.repos.discovery import Repo, find_repos

# Candidates shown in an "ambiguous" error before the list is cut off.
MAX_LISTED_CANDIDATES = 8


def looks_like_path(repo: str) -> bool:
    """Say whether the text is meant as a path rather than a repo name.

    Args:
        repo: What the caller typed.

    Returns:
        True for absolute paths or text containing a path separator.
    """
    return Path(repo).is_absolute() or "/" in repo or "\\" in repo


def resolve_repo(repo: str, repos: Sequence[Repo], roots: Iterable[Path]) -> Path:
    """Resolve a path or repo name to one absolute folder inside the roots.

    Args:
        repo: A folder path, or a repo name or unique part of one.
        repos: The discovered repos to match names against.
        roots: The configured repo roots the result must be inside.

    Returns:
        The resolved, absolute folder.

    Raises:
        RepoOutsideRootsError: The folder is a network path or outside the roots.
        RepoNotFoundError: Blank input, a path that isn't a folder, or a name
            matching no repo or several.
    """
    wanted = repo.strip()
    if not wanted:
        raise RepoNotFoundError("No repo given; pass a folder path or a repo name.")
    folder = wanted if looks_like_path(wanted) else _match_by_name(wanted, repos).path
    return require_inside_roots(folder, roots)


def locate_repo(repo: str, roots: Iterable[Path], max_depth: int) -> Path:
    """Resolve a path or repo name, scanning the roots for repos only when a name is given.

    Args:
        repo: A folder path, or a repo name or unique part of one.
        roots: Folders to search for repos (Settings.repo_roots).
        max_depth: Search depth below each root.

    Returns:
        The resolved, absolute folder.

    Raises:
        RepoNotFoundError: See resolve_repo.
    """
    roots = tuple(roots)
    if looks_like_path(repo.strip()):
        return resolve_repo(repo, (), roots)
    return resolve_repo(repo, find_repos(roots, max_depth), roots)


def _match_by_name(name: str, repos: Sequence[Repo]) -> Repo:
    """Exact name match (case-sensitive, then not), then a unique substring match."""
    # Case matters first: "OtherRepo" (the folder the owner works in) and its inner
    # git repo "Otherrepo" are both real, and the exact spelling picks one.
    exact_case = [repo for repo in repos if repo.name == name]
    if len(exact_case) == 1:
        return exact_case[0]
    wanted = name.lower()
    exact = [repo for repo in repos if repo.name.lower() == wanted]
    if len(exact) == 1:
        return exact[0]
    candidates = exact or [repo for repo in repos if wanted in repo.name.lower()]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RepoNotFoundError(f"No repo name matches {name!r}; list_repos shows them all.")
    raise RepoNotFoundError(_ambiguous_message(name, candidates))


def _ambiguous_message(name: str, candidates: Sequence[Repo]) -> str:
    """Name the matching repos so the caller can pick one by path."""
    listed = ", ".join(str(repo.path) for repo in candidates[:MAX_LISTED_CANDIDATES])
    more = len(candidates) - MAX_LISTED_CANDIDATES
    suffix = f" and {more} more" if more > 0 else ""
    return f"{name!r} matches {len(candidates)} repos ({listed}{suffix}); pass a path instead."

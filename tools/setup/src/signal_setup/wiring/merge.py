"""Merges what a plan wants into the config entries already there, by the ledger's one rule.

Setup's entries are the ones the ledger lists that the config still holds exactly as
recorded. Each merge takes out those the plan no longer wants, leaves everything else as
it is, and adds a wanted entry only where the config has none of that identity (a
server's name, a rule's text, a hook's event and module): an entry the owner made is
never replaced, and never claimed. In a list, every entry that stays keeps its place,
setup's own that are still wanted too, so a wire with nothing to add or take out changes
nothing (the order of an object's keys isn't a change). Each returns what setup owns
afterwards, for the ledger (ledger.py). Nothing here reads or writes a file.
"""

import copy
from typing import Any


def merge_named(
    current: dict[str, Any], added: dict[str, Any], wanted: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge entries kept by name (.mcp.json's servers).

    Args:
        current: The entries in the file.
        added: The ledger's: what setup wrote, by name.
        wanted: What the plan wants, by name.

    Returns:
        The entries to save, and those of them that are setup's.
    """
    kept = {
        name: entry
        for name, entry in current.items()
        if not (name in added and added[name] == entry)
    }
    owned = {name: entry for name, entry in wanted.items() if name not in kept}
    return {**kept, **owned}, owned


def merge_listed(
    current: list[Any], added: list[Any], wanted: list[Any]
) -> tuple[list[Any], list[Any]]:
    """Merge entries kept in a list (allow rules, approved server names).

    Args:
        current: The entries in the file.
        added: The ledger's: what setup wrote.
        wanted: What the plan wants.

    Returns:
        The entries to save, and those of them that are setup's.
    """
    others = list(current)  # the owner's: everything but setup's
    for entry in added:
        if entry in others:
            others.remove(entry)  # one copy only: a second one is the owner's
    owned = [entry for entry in wanted if entry not in others]
    # Setup's that are still wanted stay where they are: taking them out and adding them
    # last would reorder the list, and so rewrite the file, once the owner (or Claude
    # Code, with each approval) has added an entry after them.
    merged = list(current)
    for entry in added:
        if entry in merged and entry not in owned:
            merged.remove(entry)
    return merged + [entry for entry in owned if entry not in merged], owned


def _dicts(value: Any) -> list[dict[str, Any]]:
    """The dicts in `value` when it's a list ([] otherwise): hand-edited files can hold anything."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def hook_args(events: Any) -> set[tuple[str, str]]:
    """(event, argument) for every argument of every command hook in a settings `hooks` value.

    Setup's hooks run `-m <module>`, so (event, module) is in it when that module is
    already hooked on that event, whoever wrote the hook and in whatever group.
    """
    if not isinstance(events, dict):
        return set()
    hooks = [
        (event, hook)
        for event, groups in events.items()
        for group in _dicts(groups)
        for hook in _dicts(group.get("hooks"))
    ]
    return {
        (event, arg)
        for event, hook in hooks
        if isinstance(hook.get("args"), list)
        for arg in hook["args"]
        if isinstance(arg, str)
    }


def _group_holding(events: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
    """The group in `events` that still holds `record`'s hook exactly as recorded, or None.

    As recorded: on that event, in a group with that matcher, with that very value.
    """
    for group in _dicts(events.get(record["event"])):
        hooks = group.get("hooks")
        is_same_matcher = group.get("matcher", "") == record["matcher"]
        if is_same_matcher and isinstance(hooks, list) and record["hook"] in hooks:
            return group
    return None


def _drop_hook(events: dict[str, Any], record: dict[str, Any]) -> None:
    """Take the one hook `record` names out of `events`, if it is still there as recorded.

    Only that hook goes: its group stays while another hook is in it, and its event while
    another group is.
    """
    group = _group_holding(events, record)
    if group is None:
        return
    groups = events[record["event"]]
    group["hooks"].remove(record["hook"])
    if not group["hooks"]:
        groups[:] = [other for other in groups if other is not group]
    if not groups:
        del events[record["event"]]


def merge_hooks(
    events: dict[str, Any],
    added: list[dict[str, Any]],
    wanted: list[tuple[str, dict[str, Any]]],
    elsewhere: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Merge hooks into `events` (a settings file's `hooks` object), changing it in place.

    Args:
        events: The file's hooks: {event: [group, ...]}. Each wanted event's value must
            be a list.
        added: The ledger's hook records: {"event", "matcher", "hook"} per hook setup wrote.
        wanted: (module, record) per hook the plan wants.
        elsewhere: hook_args of another settings file Claude Code loads too. A hook there
            is already there, so it isn't added a second time here.

    Returns:
        The records of the hooks in `events` that are setup's.
    """
    others = copy.deepcopy(events)  # the owner's: every hook but setup's
    for record in added:
        _drop_hook(others, record)
    there = hook_args(others) | elsewhere
    owned = [record for module, record in wanted if (record["event"], module) not in there]
    for record in added:
        if record not in owned:
            _drop_hook(events, record)
    for record in owned:
        # One of setup's that is still wanted and still as recorded stays where it is, in
        # its group: moving it would rewrite the file with nothing to change.
        if record in added and _group_holding(events, record):
            continue
        group: dict[str, Any] = {"hooks": [record["hook"]]}
        if record["matcher"]:
            group = {"matcher": record["matcher"], **group}
        events.setdefault(record["event"], []).append(group)
    return owned

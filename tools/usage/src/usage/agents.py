"""The per-session sets of active subagents, kept from SubagentStart and SubagentStop events.

state["sessions"] maps a session id to
{"agents": [{"id", "type", "seen_at"}], "updated_at"}.
- A start adds the agent, or refreshes it if it's already there: Claude Code
  fires SubagentStart again when a subagent resumes, and for each message an
  agent team teammate handles.
- A stop removes it. Stops also fire for Claude Code's internal agents (prompt
  suggestions, /btw), which were never added, so removing an unknown id does
  nothing.
- A stop can be missed (the session closed mid-run), so an agent not seen for
  STALE_AGENT_AGE is pruned. A session with no agents left is dropped.
state["active_subagents"] is the total across sessions.
"""

from datetime import datetime, timedelta
from typing import Any

from usage.times import parse_iso, to_iso

START_EVENT = "SubagentStart"
STOP_EVENT = "SubagentStop"
# An agent killed with TaskStop, or whose session died, never fires SubagentStop,
# so it's counted until it goes stale. 6 h left killed agents showing for hours;
# 2 h still covers a long agent (over an hour). A live agent that runs over 2 h
# without a resume drops out of the count until its next start.
STALE_AGENT_HOURS = 2
STALE_AGENT_AGE = timedelta(hours=STALE_AGENT_HOURS)

Agent = dict[str, Any]
Session = dict[str, Any]


def record_subagent_event(
    state: dict[str, Any], event: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """The state with the hook event's agent added or removed, then pruned and recounted.

    Args:
        state: The current state; its sessions may be missing or malformed.
        event: The hook input (hook_event_name, session_id, agent_id, agent_type).
            Other events, or ones without both ids, only prune.
        now: The current time (aware).

    Returns:
        A new state dict; `state` isn't changed.
    """
    sessions = _valid_sessions(state.get("sessions"))
    session_id, agent_id = event.get("session_id"), event.get("agent_id")
    event_name = event.get("hook_event_name")
    if _is_id(session_id) and _is_id(agent_id) and event_name in (START_EVENT, STOP_EVENT):
        agents = {agent["id"]: agent for agent in sessions.get(session_id, {}).get("agents", [])}
        if event_name == START_EVENT:
            agents[agent_id] = _new_agent(agent_id, event.get("agent_type"), now)
        else:
            agents.pop(agent_id, None)
        sessions[session_id] = {"agents": list(agents.values()), "updated_at": to_iso(now)}
    return prune_subagents({**state, "sessions": sessions}, now)


def prune_subagents(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    """The state without agents older than STALE_AGENT_AGE or empty sessions, recounted.

    Returns:
        A new state dict with "sessions" and "active_subagents" set.
    """
    sessions: dict[str, Session] = {}
    for session_id, session in _valid_sessions(state.get("sessions")).items():
        live = [agent for agent in session["agents"] if _is_live(agent, now)]
        if live:
            sessions[session_id] = {**session, "agents": live}
    total = sum(len(session["agents"]) for session in sessions.values())
    return {**state, "sessions": sessions, "active_subagents": total}


def _new_agent(agent_id: str, agent_type: object, now: datetime) -> Agent:
    return {
        "id": agent_id,
        "type": agent_type if isinstance(agent_type, str) else "",
        "seen_at": to_iso(now),
    }


def _is_live(agent: Agent, now: datetime) -> bool:
    seen = parse_iso(agent.get("seen_at"))
    return seen is not None and now - seen < STALE_AGENT_AGE


def _valid_sessions(value: object) -> dict[str, Session]:
    """The well-formed sessions and agents from the state file (read back from disk)."""
    if not isinstance(value, dict):
        return {}
    sessions: dict[str, Session] = {}
    for session_id, session in value.items():
        if isinstance(session, dict) and isinstance(session.get("agents"), list):
            agents = [a for a in session["agents"] if isinstance(a, dict) and _is_id(a.get("id"))]
            sessions[session_id] = {**session, "agents": agents}
    return sessions


def _is_id(value: object) -> bool:
    return isinstance(value, str) and bool(value)

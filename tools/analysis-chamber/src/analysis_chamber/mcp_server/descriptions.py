"""Model-facing text for the chamber MCP tools: the descriptions ARE the UX.

They tell the calling chat how to run the plan check with the user and when to publish.
"""

SERVER_INSTRUCTIONS = (
    "The analysis chamber plans, runs and answers questions about deep analyses. "
    "Flow: chamber_start, show the user the plan, chamber_approve with the answers, "
    "chamber_status to follow it, chamber_ask for questions about a run."
)

CHAMBER_START = (
    "Start an analysis run for a question. Returns {run_id, plan}; nothing runs yet. "
    "Show the plan to the user and ask two things every time: OK or tweaks, AND whether the "
    "run is personal (yes/no). Do not skip the personal question and do not answer it yourself. "
    "Then call chamber_approve. To cancel a run, the user uses the CLI: "
    "`analysis-chamber cancel <id>`."
)

CHAMBER_APPROVE = (
    "Approve a run's plan, or send tweaks. `edits`: the user's plan changes as free text; "
    "with edits the plan is revised and stays unapproved, so show the new plan and ask again. "
    "`personal`: true or false, taken only from the user's answer to the personal question. "
    "Never guess it, "
    "never default it; leave it unset until it has been answered. Approval needs `personal` set."
)

CHAMBER_STATUS = (
    "Status of one run: phase, percent, status, outputs, and the report location when done. "
    "When the result has a `publish` field, publish that html file with your Artifact tool and "
    "give the user the link. Never publish otherwise: the field only appears for runs that are "
    "allowed to be published, never for personal runs."
)

CHAMBER_LIST = (
    "List every run (active, queued and finished) with its id, status, phase and percent."
)

CHAMBER_ASK = (
    "Ask a question about a run's analysis, answered from its results. While the run is "
    "unfinished the answer is flagged as partial."
)

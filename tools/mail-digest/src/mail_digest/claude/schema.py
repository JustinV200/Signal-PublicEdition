"""The JSON schema for the routine's structured output (claude --json-schema).

The schema shapes what the model returns; result.py still validates every field,
because the model has read untrusted email. The runner works out the completed
accounts and what to announce itself (mailbox/, deadlines/), so the model returns
only what needs judgement: the emails that tried to steer it, and its summary.
"""

import json


def output_schema(aliases: tuple[str, ...]) -> str:
    """The schema passed to --json-schema, as a compact string."""
    alias = {"type": "string", "enum": list(aliases)}
    schema = closed_object(
        suspicious=array_of(alias=alias, message_id={"type": "string"}, sender={"type": "string"}),
        summary={"type": "string"},
    )
    return json.dumps(schema, separators=(",", ":"))


def closed_object(**properties: dict) -> dict:
    """A closed object schema with every property required (the checker's schemas use it too)."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def array_of(**properties: dict) -> dict:
    """An array of closed objects with these properties."""
    return {"type": "array", "items": closed_object(**properties)}

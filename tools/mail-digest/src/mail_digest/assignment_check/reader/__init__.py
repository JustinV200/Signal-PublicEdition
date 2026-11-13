"""assignment_check.reader: the tool-less claude that turns one site's page text into items."""

from mail_digest.assignment_check.reader.command import (
    ITEM_KINDS,
    READER_LOCKDOWN,
    reader_command,
    reader_schema,
)
from mail_digest.assignment_check.reader.context import (
    SITE_FRAME_TAG,
    ReaderContext,
    reader_context,
)
from mail_digest.assignment_check.reader.output import ReaderItem, ReaderOutput, parse_reader

__all__ = [
    "ITEM_KINDS",
    "READER_LOCKDOWN",
    "SITE_FRAME_TAG",
    "ReaderContext",
    "ReaderItem",
    "ReaderOutput",
    "parse_reader",
    "reader_command",
    "reader_context",
    "reader_schema",
]

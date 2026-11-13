"""html_to_text: plain text from an HTML email body, with the stdlib html.parser.

Scripts, styles and similar non-content elements are dropped. Block elements
become line breaks, list items get a "- " bullet, and whitespace is tidied, so
the model gets readable text without markup.
"""

import re
from html.parser import HTMLParser

# Elements whose text is never part of the message a person reads.
SKIPPED_TAGS = frozenset({"script", "style", "title", "noscript", "template"})
BLOCK_TAGS = frozenset(
    {
        "address", "article", "blockquote", "br", "div", "footer", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "li", "ol", "p", "pre", "section", "table", "tr", "ul",
    }
)  # fmt: skip
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


class _TextCollector(HTMLParser):
    """Gathers text outside skipped elements, adding line breaks around blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n- " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_TAGS and tag != "br":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Convert an HTML document or fragment to readable plain text.

    Args:
        html: The HTML (entities are decoded).

    Returns:
        The text, with runs of spaces collapsed and at most one blank line in a row.
    """
    collector = _TextCollector()
    collector.feed(html)
    collector.close()
    # str.split() also splits on non-breaking spaces, which HTML mail is full of.
    lines = (" ".join(line.split()) for line in "".join(collector.parts).splitlines())
    return _EXTRA_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()

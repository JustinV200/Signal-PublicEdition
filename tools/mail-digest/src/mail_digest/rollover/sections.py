"""Splits a week file into its `## ` sections and joins them back, for the rollover.

The plan and the review are built by appending lines under the template's headings,
so both use this. Lines before the first `## ` heading (the `# ` title) are the
preamble.
"""

from dataclasses import dataclass, field

SECTION_PREFIX = "## "


@dataclass
class Section:
    """One `## ` heading and the lines under it (no leading or trailing blank lines)."""

    heading: str
    lines: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """The heading compared ignoring case and spacing, e.g. "## overdue"."""
        return " ".join(self.heading.split()).casefold()


@dataclass
class WeekFile:
    """A week file as its preamble and its sections, in order."""

    preamble: list[str]
    sections: list[Section]

    def ensure_section(self, heading: str, is_first: bool = False) -> Section:
        """The section with this heading (compared like Section.key), added if missing.

        A missing section goes first if is_first, else last.
        """
        key = Section(heading).key
        found = next((s for s in self.sections if s.key == key), None)
        if found is None:
            found = Section(heading)
            self.sections.insert(0 if is_first else len(self.sections), found)
        return found


def split_sections(text: str) -> WeekFile:
    """Parse text (any line endings) into its preamble and sections."""
    preamble: list[str] = []
    sections: list[Section] = []
    for line in text.splitlines():
        if line.startswith(SECTION_PREFIX):
            sections.append(Section(line.rstrip()))
        elif sections:
            sections[-1].lines.append(line)
        else:
            preamble.append(line)
    # Trimmed now, so lines appended later sit right under the section's last line.
    for section in sections:
        section.lines = _trimmed(section.lines)
    return WeekFile(_trimmed(preamble), sections)


def join_sections(week_file: WeekFile) -> str:
    """The file as LF text: the preamble, then each section, one blank line between."""
    blocks = ["\n".join(_trimmed(week_file.preamble))]
    blocks += ["\n".join([s.heading, *_trimmed(s.lines)]) for s in week_file.sections]
    return "\n\n".join(block for block in blocks if block) + "\n"


def _trimmed(lines: list[str]) -> list[str]:
    """lines without leading or trailing blank lines."""
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]

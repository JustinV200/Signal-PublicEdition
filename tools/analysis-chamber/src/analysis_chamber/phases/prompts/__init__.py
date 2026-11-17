"""The agent prompt templates (the *.md files here) and the one function that fills them.

Templates use string.Template `$name` placeholders, so Markdown braces are safe.
"""

from functools import cache
from importlib import resources
from string import Template


@cache
def _template(name: str) -> Template:
    """The parsed template `<name>.md` from this folder."""
    text = resources.files(__name__).joinpath(f"{name}.md").read_text(encoding="utf-8")
    return Template(text)


def render(name: str, **values: object) -> str:
    """Fill prompt template `name` with values.

    Raises:
        FileNotFoundError: No such template.
        KeyError: A placeholder in the template has no value.
    """
    return _template(name).substitute(values).strip()

"""Sanitize SVG markup before it is stored in the scene and injected into the board page.

The board page runs DOMPurify on SVG too; this is the server-side layer, so a bad
item never even reaches scene.json. It strips:
- scripting elements (`<script>`, `<foreignObject>`, embeds) and non-SVG-namespace elements
- `<style>` elements: a stylesheet in one item would restyle the whole board page, and
  could light up layers the page hides (the night view, the TODO view, a clean capture's
  blank page). Inline `style` attributes stay; they only reach their own element.
- `on*` event-handler attributes
- hrefs that aren't same-document `#fragment` references
- `javascript:` values and `url(...)` references to anything but `#fragment`
- animations that would rewrite an href or event handler
"""

import re
import xml.etree.ElementTree as ElementTree

from whiteboard.display.scene.model import SceneError

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
# Big enough for any hand-written diagram, small enough to bound parse time.
MAX_SVG_CHARS = 500_000

# Lower-cased local names of elements that can run script, embed documents, load HTML,
# or (style) restyle the rest of the board page.
_BLOCKED_ELEMENTS = frozenset(
    {"script", "foreignobject", "iframe", "embed", "object", "handler", "style"}
)
_ANIMATION_ELEMENTS = frozenset({"set", "animate", "animatetransform", "animatemotion"})
_JAVASCRIPT_URL = re.compile(r"j\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t\s*:", re.IGNORECASE)
# url( followed by anything except an optional quote and '#'.
_EXTERNAL_CSS_URL = re.compile(r"url\(\s*['\"]?\s*(?!#)", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"@import", re.IGNORECASE)

# Serialize SVG with a default namespace instead of "ns0:" prefixes. This is
# module-wide ElementTree state, and nothing else in the process relies on it.
ElementTree.register_namespace("", SVG_NAMESPACE)
ElementTree.register_namespace("xlink", XLINK_NAMESPACE)


def sanitize_svg(markup: str) -> str:
    """Parse SVG markup and return it re-serialized with every dangerous part removed.

    Args:
        markup: Untrusted SVG source whose root element must be `<svg>`.

    Returns:
        The cleaned SVG markup.

    Raises:
        SceneError: If the markup is too large, isn't well-formed XML, or its root isn't `<svg>`.
    """
    if len(markup) > MAX_SVG_CHARS:
        raise SceneError(f"svg content is over {MAX_SVG_CHARS} characters")
    try:
        root = ElementTree.fromstring(markup)
    except ElementTree.ParseError as error:
        raise SceneError(f"svg content is not well-formed XML: {error}") from error
    if _local_name(root.tag) != "svg" or not _is_svg_namespace(root.tag):
        raise SceneError("svg content must have an <svg> root element")
    _clean_tree(root)
    try:
        return ElementTree.tostring(root, encoding="unicode")
    except RecursionError as error:
        raise SceneError("svg content is nested too deeply") from error


def _clean_tree(root: ElementTree.Element) -> None:
    # Iterative walk: deeply nested input must not hit Python's recursion limit here.
    _clean_attributes(root)
    stack = [root]
    while stack:
        parent = stack.pop()
        for child in list(parent):
            if _is_blocked(child):
                parent.remove(child)
                continue
            _clean_attributes(child)
            stack.append(child)


def _is_blocked(element: ElementTree.Element) -> bool:
    # Comments and processing instructions have a non-string tag; ElementTree's
    # default parser already drops them, but be safe.
    if not isinstance(element.tag, str) or not _is_svg_namespace(element.tag):
        return True
    name = _local_name(element.tag).lower()
    if name in _BLOCKED_ELEMENTS:
        return True
    if name in _ANIMATION_ELEMENTS:
        # attributeName is a qualified name like "xlink:href", so drop any prefix.
        target = element.get("attributeName", "").rsplit(":", 1)[-1].strip().lower()
        return target == "href" or target.startswith("on")
    return False


def _clean_attributes(element: ElementTree.Element) -> None:
    for key, value in list(element.attrib.items()):
        if _is_unsafe_attribute(_local_name(key).lower(), value):
            del element.attrib[key]


def _is_unsafe_attribute(name: str, value: str) -> bool:
    if name.startswith("on"):
        return True
    if name == "href" and not value.strip().startswith("#"):
        return True
    return bool(_JAVASCRIPT_URL.search(value)) or _has_external_reference(value)


def _has_external_reference(css_or_value: str) -> bool:
    return bool(_EXTERNAL_CSS_URL.search(css_or_value) or _CSS_IMPORT.search(css_or_value))


def _is_svg_namespace(tag: str) -> bool:
    # No namespace at all is fine: the HTML parser treats a bare <svg> subtree as SVG.
    return not tag.startswith("{") or tag.startswith("{" + SVG_NAMESPACE + "}")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

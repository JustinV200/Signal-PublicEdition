"""Sort sensitive actions into "ask the owner" and "run it, but log it".

Every rule that finds an action sensitive names a category (purchase, send,
delete; see browser_tool.config) or None, for rules that only ever log (an
element in a frame of unverified origin, an ordinary key press).
A category listed in [gates] always_confirm asks; any other only logs. The
owner's own [gates] patterns always ask. Text matching is ActionRules'
case-insensitive regex search, one ActionRules per category.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace

from browser_tool.gates.action_rules import ActionRules

# The category of the owner's own [gates] patterns, which always ask.
CUSTOM_CATEGORY = "custom"


@dataclass(frozen=True)
class GateCheck:
    """Why an action is sensitive, and whether it waits for the owner.

    Attributes:
        reason: Shown in the dialog and the log, e.g. "matches the send rule \\bsend\\b".
        must_confirm: True: ask the owner. False: run it and log it.
        asking: Every category among the merged checks that asks (strictest
            unions them), so a re-check can tell "send" from "send and delete".
            Left out of equality, which compares the verdict itself.
    """

    reason: str
    must_confirm: bool
    asking: frozenset[str] = field(default=frozenset(), compare=False)


class ConfirmRules:
    """The sensitive-action rules, and which of their categories ask the owner."""

    def __init__(
        self,
        category_patterns: Mapping[str, Sequence[str]],
        always_confirm: Collection[str],
        extra_patterns: Sequence[str] = (),
    ):
        """Compile every category's patterns.

        Args:
            category_patterns: Category name -> its regexes, tried in this order.
            always_confirm: The categories that ask the owner.
            extra_patterns: The owner's own regexes; a match always asks.

        Raises:
            re.error: If a pattern is not a valid regex (config validates this first).
        """
        self._rules = {name: ActionRules(patterns) for name, patterns in category_patterns.items()}
        self._rules[CUSTOM_CATEGORY] = ActionRules(extra_patterns)
        self._asking = {*always_confirm, CUSTOM_CATEGORY}

    def check(self, category: str | None, reason: str) -> GateCheck:
        """A GateCheck for `reason`, asking only if `category` is set to ask.

        Args:
            category: The rule's category, or None for a rule that only logs.
            reason: Why the action is sensitive.
        """
        must_confirm = category in self._asking
        asking = frozenset({category}) if must_confirm and category else frozenset()
        return GateCheck(reason, must_confirm, asking)

    def check_texts(self, texts: Sequence[str]) -> GateCheck | None:
        """Match `texts` against every category; None if nothing matches.

        A match in an asking category wins over one that only logs.
        """
        found = [
            self.check(category, f"matches the {category} rule {pattern}")
            for category, rules in self._rules.items()
            if (pattern := rules.find_match(texts))
        ]
        return strictest(*found)


def strictest(*checks: GateCheck | None) -> GateCheck | None:
    """The first check that asks the owner, else the first one, else None.

    The result's `asking` is the union of every check's asking categories.
    """
    present = [check for check in checks if check is not None]
    if not present:
        return None
    # max() keeps the first of equal items, so rule order decides the reason shown.
    chosen = max(present, key=lambda check: check.must_confirm)
    return replace(chosen, asking=frozenset().union(*(check.asking for check in present)))

"""mail_digest.claude.prompt: the composed system prompt is the routine, then the shared rules."""

from mail_digest.claude import compose_prompt
from mail_digest.settings import PROMPT_PATH, SHARED_RULES_PATH


def test_the_digest_prompt_ends_with_the_rules_with_its_tag_filled_in(tmp_path):
    text = compose_prompt(PROMPT_PATH, "(mail)", tmp_path / "p.md").read_text(encoding="utf-8")
    rules = SHARED_RULES_PATH.read_text(encoding="utf-8").replace("{tag}", "(mail)")
    assert text.startswith(PROMPT_PATH.read_text(encoding="utf-8").rstrip())
    assert text.endswith(rules)
    assert "{tag}" not in text and "with ` (mail)`" in text

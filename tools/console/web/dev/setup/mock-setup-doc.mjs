// The mock `setup doc <tool> <step>` (tools/setup cli/doc.py): a short made-up
// guide for any step whose registry entry names one, so the wizard's inline
// guide has Markdown to render. It is never a real guide's text. The copytone
// guide stands for one this copy doesn't ship: exit 1 and one plain sentence.
// Used by mock-setup-cli.mjs.

const EXIT_NO_GUIDE = 1;
const MISSING_GUIDES = new Set([".claude/skills/copytone/SKILL.md"]);

/** A generic guide: headings, steps with a link, code, and HTML that must stay text. */
const guideText = (doc) => [
  `# Example guide (${doc})`,
  "",
  "A made-up guide from the mock; the real wizard shows the file this step names.",
  "",
  "## Steps",
  "",
  "1. Open https://example.com/console and create a project.",
  "2. Save its client file as `tools/example/client.json`.",
  "3. Come back and click **I did this: mark done**.",
  "",
  "```",
  "uv run --project tools/example --frozen --no-sync example check",
  "```",
  "",
  "<b>Raw HTML</b> stays text, and [a relative link](../other.md) stays plain.",
];

/**
 * What `setup doc` prints for the step `findStep` found.
 *
 * @param {{step?: object, error?: string}} found mock-setup-cli.mjs's findStep result.
 * @param {(why: string) => {lines: string[], exit: number}} badId Its exit-2 answer.
 * @returns {{lines: string[], exit: number}} The guide (exit 0) or why there's none.
 */
export function guideAnswer({ step, error }, badId) {
  if (error) return badId(error);
  if (!step.doc) return { lines: ["This step has no guide."], exit: EXIT_NO_GUIDE };
  if (MISSING_GUIDES.has(step.doc)) {
    const why = `The guide for this step (${step.doc}) isn't in this copy of Signal.`;
    return { lines: [why], exit: EXIT_NO_GUIDE };
  }
  return { lines: guideText(step.doc), exit: 0 };
}

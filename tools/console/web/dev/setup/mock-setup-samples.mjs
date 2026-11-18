// The mock setup CLI's writing samples (`setup samples files|paste|mail|keep|count`,
// cli/agent.py samples_command): each action's JSON documents, ending with the
// running count, like tools/setup/src/signal_setup/samples. Nothing is read or
// saved: the count lives in memory, and "sent mail" is two neutral rows.
// Used by mock-setup-cli.mjs, which prints the documents.

// samples/store.py TARGET_RANGE, as the CLI prints it.
const TARGET = "5-15";
const MAX_NAME_CHARS = 40;
// What `samples mail` offers: recent sent mails with only the owner's own text,
// each 30 words or more, since the real fetch_sent drops shorter ones.
const SENT_MAIL = [
  {
    number: 1,
    subject: "Re: Saturday plans",
    text: "Thanks for organising this. I can bring the folding chairs and a cooler, and I will be there by ten to help set up. Let me know if anything changes before then, or if you need anything else picked up on the way.",
  },
  {
    number: 2,
    subject: "Notes from the planning call",
    text: "Here is a short summary of what we agreed: the draft goes out on Friday, everyone sends comments by Monday, and we meet again the week after to settle the open questions. Shout if I missed anything important.",
  },
];

// Samples saved so far; the mock starts part of the way to the target.
let sampleCount = 3;

/** A sample file's name stem, as store.py slugs it. */
const slug = (name) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, MAX_NAME_CHARS) || "sample";

/** The last name in a Windows or POSIX path, without its extension. */
const stem = (path) => (path.split(/[\\/]/).filter(Boolean).at(-1) ?? "").replace(/\.[^.]*$/, "");

/** Counts `names` as saved and returns them. */
function saved(names) {
  sampleCount += names.length;
  return names;
}

/** The action's own document, or null when it prints only the count. */
function actionDoc({ action, kind = "writing", paths, numbers }) {
  if (action === "files") {
    const names = saved(paths.map((path) => `${kind}-${slug(stem(path))}.md`));
    return names.map((name) => `added ${name}`);
  }
  if (action === "paste") return saved([`${kind}-pasted.md`]);
  if (action === "mail") return SENT_MAIL;
  if (action === "keep") {
    const kept = SENT_MAIL.filter((mail) => numbers.includes(mail.number));
    return saved(kept.map((mail) => `email-${slug(mail.subject)}.md`));
  }
  return null;
}

/**
 * The JSON documents `setup samples <action>` prints, in order: the action's
 * own (none for count), then `{samples, target}`.
 *
 * @param {object} request The page's samples request, its shape already checked.
 * @returns {object[]} The documents to print.
 */
export function samplesDocs(request) {
  const doc = actionDoc(request);
  return [...(doc ? [doc] : []), { samples: sampleCount, target: TARGET }];
}

// The mock backend's starting data: a few chat, action, voice and note events
// so every row kind shows on first load (two action rows back to back, and a
// long reply with headings and tables), and the Claude session's state, which
// `--claude` can start in each state the status line words, and `--news-every`'s
// live rows (the Chat tab's `N new`; with `--long-news` each reply is taller
// than the view). Split out of mock-server.mjs.
const MS_PER_MINUTE = 60_000;
// How long a stale turn has been quiet: the status line reads `quiet for 12 min`.
const QUIET_MINUTES = 12;
const MS_PER_DAY = 24 * 60 * MS_PER_MINUTE;
const CLAIM_AGE_DAYS = 3;
// `--long-news` replies have this many lines: taller than a 720px window.
const LONG_REPLY_LINES = 60;
// How long a `--news-every` reply's turn shows Claude working before the reply lands.
const NEWS_TURN_MS = 1000;

export const REPLY = [
  "Sent `lecture` to the projector. Due this week:",
  "",
  "- Statistics problem set 4 (Thu)",
  "- Club demo notes, see `life/areas/club/`",
  "- [ ] reply to the county email (Fri)",
  "",
  "The plan is in [the week folder](https://example.com/week). Raw HTML like <b>this</b> stays text, and `javascript:` links do not render: [nope](javascript:alert(1)).",
  "",
  "```sh",
  "git log --oneline -3",
  "```",
].join("\n");

// A long reply with paragraphs, two h2 sections, an ASCII table in a code
// block and a markdown table: the chat's paragraph and message rhythm and
// table alignment are judged on it.
export const LONG_REPLY = [
  "Here is where the three builds stand. Two passed their checks this morning, and the third is waiting on a flaky test that failed once in five runs.",
  "",
  "The flaky one is the cache test. It passes alone and fails only when the whole suite runs, so it is probably sharing a temp folder with another test.",
  "",
  "## Builds",
  "",
  "```text",
  "┌──────────┬────────┬────────┬──────────┐",
  "│ build    │ status │ tests  │ duration │",
  "├──────────┼────────┼────────┼──────────┤",
  "│ web      │ passed │ 174    │ 41s      │",
  "│ backend  │ passed │ 312    │ 1m 08s   │",
  "│ worker   │ flaky  │ 88 / 1 │ 2m 15s   │",
  "└──────────┴────────┴────────┴──────────┘",
  "```",
  "",
  "| step  | owner  | next           |",
  "| ----- | ------ | -------------- |",
  "| fix   | Claude | own temp dir   |",
  "| rerun | Claude | five full runs |",
  "",
  "## Next",
  "",
  "I'll give the cache test its own temp folder and rerun the suite five times. If it stays green, the worker build goes to review.",
].join("\n");

// The real server derives this from the turn hooks; here a reply ends the turn.
export function turnState(working) {
  const at = Date.now();
  return {
    state: working ? "working" : "idle",
    startedAt: working ? at : null,
    lastActivityAt: at,
    agents: 0,
    agentsUnsure: false,
  };
}

/**
 * The orchestrator block to start with. `mode` (from `--claude`): `none` never
 * claimed, `closed` claimed but its session gone, `quiet` a turn with no hook
 * for 12 min, `unknown` no hook yet; anything else is a live, idle session.
 */
export function startOrchestrator(mode) {
  const claimed = mode !== "none";
  // Claimed three days ago, so the status line's tooltip shows `linked 3d ago`.
  const claimedAt = claimed
    ? new Date(Date.now() - CLAIM_AGE_DAYS * MS_PER_DAY).toISOString()
    : null;
  const alive = claimed && mode !== "closed";
  const orchestrator = { claimed, alive, label: "main", claimedAt };
  if (mode === "quiet") {
    const quietSince = Date.now() - QUIET_MINUTES * MS_PER_MINUTE;
    const turn = { ...turnState(true), state: "stale", startedAt: quietSince };
    return { ...orchestrator, turn: { ...turn, lastActivityAt: quietSince } };
  }
  if (mode === "unknown") {
    const turn = { ...turnState(false), state: "unknown", lastActivityAt: null };
    return { ...orchestrator, turn };
  }
  return { ...orchestrator, turn: turnState(false) };
}

export function seedHistory(emit, newId) {
  const base = Date.now() - 20 * MS_PER_MINUTE;
  const at = (minutes) => new Date(base + minutes * MS_PER_MINUTE).toISOString();
  emit("message", {
    id: newId("m"),
    role: "you",
    kind: "chat",
    at: at(0),
    text: "load the lecture board and tell me what's due this week",
  });
  emit("message", {
    id: newId("m"),
    role: "you",
    kind: "action",
    at: at(0),
    text: 'Send to projector: "lecture"',
  });
  // Two action rows back to back: they sit closer than separate messages.
  emit("message", { id: newId("m"), role: "you", kind: "action", at: at(0), text: "Start voice" });
  emit("message", { id: newId("m"), role: "claude", kind: "chat", at: at(1), text: REPLY });
  emit("message", {
    id: newId("m"),
    role: "claude",
    kind: "chat",
    at: at(3),
    text: "Background: the Spotify search fix passed review and is pushed as `a0f8b46`. Nothing is waiting on you.",
  });
  emit("voice", {
    id: newId("v"),
    kind: "heard",
    at: at(2),
    text: "Hey Claude, what's on the board right now?",
  });
  emit("voice", {
    id: newId("v"),
    kind: "said",
    at: at(2.1),
    text: "The to-do list, with four open items. The top one is the statistics problem set.",
  });
  emit("voice", {
    id: newId("v"),
    kind: "note",
    at: at(4),
    text: "permission: Spotify play? answered yes",
  });
  emit("note", {
    id: newId("n"),
    at: at(5),
    text: 'Messages now go to the session labelled "console-review" (linked just now).',
  });
  emit("message", {
    id: newId("m"),
    role: "you",
    kind: "chat",
    at: at(6),
    text: "how are the builds doing?",
  });
  emit("message", { id: newId("m"), role: "claude", kind: "chat", at: at(7), text: LONG_REPLY });
}

/** A news reply: one line, or (with `long`) a numbered list taller than the view. */
function newsText(count, long) {
  const head = `Background update ${count}: a task moved to review.`;
  if (!long) return head;
  const lines = Array.from({ length: LONG_REPLY_LINES }, (_, i) => `${i + 1}. line ${i + 1}`);
  return [head, "", ...lines].join("\n");
}

/**
 * Every `seconds`, a live row lands with no message sent: an unprompted Claude
 * reply, then a console note, in turn. Lets a screen check raise the Chat tab's
 * `N new` while another view is open. `long` makes each reply taller than the
 * view, for following a long reply from its top. With `setBusy` each reply
 * comes in a turn: working for NEWS_TURN_MS, then the reply and the turn's end
 * back to back, as a send's reply does.
 */
export function startNews(emit, newId, seconds, { long = false, setBusy } = {}) {
  // A bad value (NaN, 0, negative) would fire on every tick: no news instead.
  if (!(seconds > 0)) return;
  let count = 0;
  setInterval(() => {
    count += 1;
    if (count % 2 === 0) {
      emit("note", {
        id: newId("n"),
        at: new Date().toISOString(),
        text: `Console note ${count}.`,
      });
      return;
    }
    const text = newsText(count, long);
    setBusy?.(true);
    setTimeout(
      () => {
        emit("message", {
          id: newId("m"),
          role: "claude",
          kind: "chat",
          at: new Date().toISOString(),
          text,
        });
        setBusy?.(false);
      },
      setBusy ? NEWS_TURN_MS : 0,
    );
  }, seconds * 1000);
}

// The mock backend's starting conversation: a few chat, action, voice and note
// events so every row kind shows on first load. Split out of mock-server.mjs.
const MS_PER_MINUTE = 60_000;

export const REPLY = [
  "Loaded `lecture` on the board. Due this week:",
  "",
  "- HIST 205 problem set 4 (Thu)",
  "- Club demo notes, see `life/areas/club/`",
  "- [ ] reply to the county email (Fri)",
  "",
  "The plan is in [the week folder](https://github.com/your-account/Signal). Raw HTML like <b>this</b> stays text, and `javascript:` links do not render: [nope](javascript:alert(1)).",
  "",
  "```sh",
  "git log --oneline -3",
  "```",
].join("\n");

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
    text: "Load whiteboard board 'lecture'",
  });
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
    text: "The TODO list, with four open items. The top one is the ML problem set.",
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
    text: "orchestrator changed: messages now go to session 'console-review', not your usual orchestrator",
  });
}

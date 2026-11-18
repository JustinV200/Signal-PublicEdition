// The mock backend's model strip block (signal_console.models): what the
// orchestrator runs now and next, the voice hub's picks, and every choice the
// pickers offer, and `applyPick` for POST /api/models. Split out of mock-server.mjs.
export const MODELS = {
  orchestrator: {
    now: { model: "claude-opus-5-5", effort: "medium" },
    next: { model: null, effort: "high" },
  },
  voice: { model: null, effort: null },
  choices: {
    orchestrator: {
      model: [
        null,
        "default",
        "best",
        "fable",
        "opus",
        "sonnet",
        "haiku",
        "opus[1m]",
        "sonnet[1m]",
        "opusplan",
      ],
      effort: [null, "low", "medium", "high", "xhigh"],
    },
    voice: {
      model: [
        "default",
        "best",
        "fable",
        "opus",
        "sonnet",
        "haiku",
        "opus[1m]",
        "sonnet[1m]",
        "opusplan",
      ],
      effort: ["low", "medium", "high", "xhigh"],
    },
  },
};

/**
 * Applies a model strip pick to `models` in place, like the real server's
 * apply_pick (orchestrator picks are for the next session).
 *
 * @param {object} models The live models block (MODELS).
 * @param {{target?: unknown, field?: unknown, index?: unknown}} pick The request body.
 * @returns {string | null} Why the pick is refused, or null when applied.
 */
export function applyPick(models, { target, field, index }) {
  const choices = models.choices[target]?.[field];
  if (!Array.isArray(choices) || !Number.isInteger(index) || !(index in choices))
    return "no such choice";
  const holder = target === "orchestrator" ? models.orchestrator.next : models.voice;
  holder[field] = choices[index];
  return null;
}

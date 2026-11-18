// Adding the finished tools to Claude Code: `setup wire`, which writes their
// servers, rules and hooks into .mcp.json and .claude/settings.local.json on
// the owner's click. Claude Code reads those files when it starts, so whoever
// holds this shows the restart line (AddResult) once `added` is true, and it
// stays until the owner moves on. Used by the wizard (kept above its screens,
// so Summary still knows) and System's tools list.
import { useCallback, useState } from "react";
import { useSetupRun } from "./useSetupRun";
import type { SetupRun } from "./useSetupRun";

/** The button's label wherever a tool can be added. */
export const ADD_TO_CLAUDE = "Add to Claude Code";
/** What the run's log says was being done (and what a hand-off names). */
export const ADD_WHAT = "Adding the tools to Claude Code (setup wire)";

export interface AddToClaude {
  /** The wire run, for its OutputLog and pending state. */
  runner: SetupRun;
  /** True once a wire worked while this was mounted. */
  added: boolean;
  /** Runs `setup wire`; resolves true when it worked. */
  add: () => Promise<boolean>;
}

/** One `setup wire` runner and whether it has worked yet. */
export function useAddToClaude(): AddToClaude {
  const runner = useSetupRun();
  const [added, setAdded] = useState(false);
  const { run } = runner;
  const add = useCallback(async () => {
    const result = await run({ command: "wire" });
    const worked = result?.exit === 0;
    if (worked) setAdded(true);
    return worked;
  }, [run]);
  return { runner, added, add };
}

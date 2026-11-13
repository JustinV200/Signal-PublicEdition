// Where the wizard opens, worked out once the tool list has loaded: the tool
// a Tools page button or `#t=<tool>` asked for (picking it first if it isn't
// picked yet), else where setup stopped (wizardScreens.resumeIndex). After
// that the owner moves with the strip, Back and Next; finishing a step never
// jumps the wizard by itself. Picking is tried once per tool: if it fails (say
// a 409 while another step runs) the wizard opens where it stopped and says why.
import { useEffect, useRef, useState } from "react";
import { runSetup } from "../../api";
import type { SetupTool } from "../../api";
import { useStore } from "../../state";
import { buildScreens, isChosen, resumeIndex } from "./wizardScreens";

/** The current screen index (null until the tools load), its setter, and why a pick failed. */
export function useStartScreen(tools: SetupTool[] | null, reload: () => void) {
  const { state, dispatch } = useStore();
  const [index, setIndex] = useState<number | null>(null);
  const [pickError, setPickError] = useState<string | null>(null);
  // Tools a pick was already tried for, so a failing `choose` never loops.
  const triedRef = useRef(new Set<string>());
  const target = state.setupTool;
  const asked = tools && target ? tools.find((tool) => tool.id === target) : undefined;
  const needsPick = asked !== undefined && !isChosen(asked);

  // Set during render (React's "adjust state when props change"), so nothing flashes.
  if (tools && !needsPick && (target || index === null)) {
    const start = resumeIndex(buildScreens(tools), tools, target);
    if (start !== index) setIndex(start);
  }

  useEffect(() => {
    if (!tools || !target) return;
    if (needsPick && !triedRef.current.has(target)) {
      // A Set up click on a tool that isn't picked yet adds it to the picks first.
      triedRef.current.add(target);
      const ids = [...tools.filter(isChosen).map((tool) => tool.id), target];
      runSetup({ command: "choose", tools: ids })
        .then((result) => {
          if (result.exit !== 0) throw new Error(result.lines.at(-1) ?? `exit ${result.exit}`);
          setPickError(null);
        })
        .catch((failure: unknown) => {
          const why = failure instanceof Error ? failure.message : String(failure);
          setPickError(`Couldn't add ${target} to your picks: ${why}`);
          dispatch({ type: "openSetup", tool: null }); // open where setup stopped instead
        })
        .finally(reload);
      return;
    }
    if (needsPick) return; // tried already; its result is on the way
    dispatch({ type: "openSetup", tool: null }); // the jump is done; forget it
  }, [tools, target, needsPick, reload, dispatch]);

  return { index, setIndex, pickError };
}

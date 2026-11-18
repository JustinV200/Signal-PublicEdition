// Which wizard page is open, once the tool list has loaded: the page kept in
// the store (`setupPage`, set by the strip, Back and Next, or by a System
// tools row's button or `#t=<tool>` asking for a tool), so leaving Setup and
// coming back lands on it again; else, on the first visit or when that page
// is gone (its tool unpicked), where setup stopped
// (wizardScreens.resumeIndex), which is then kept too (pageToKeep). So
// finishing a step never jumps the wizard by itself. A tool asked for that
// isn't picked yet is picked first, tried once per tool: if it fails (say a
// 409 while another step runs) the wizard opens where it stopped and says why.
import { useEffect, useRef, useState } from "react";
import { runSetup } from "../../api";
import type { SetupTool } from "../../api";
import { useStore } from "../../state";
import { buildScreens, isChosen, openIndex, pageToKeep, screenKey } from "./wizardScreens";

/**
 * The wizard's pages and the open one.
 *
 * @param tools The `setup list` answer; null until it loads.
 * @param reload Reads the list again (after a pick).
 * @returns The pages, the open page's index (null until the tools load), its setter
 *   and why a pick failed.
 */
export function useStartScreen(tools: SetupTool[] | null, reload: () => void) {
  const { state, dispatch } = useStore();
  const [pickError, setPickError] = useState<string | null>(null);
  // Tools a pick was already tried for, so a failing `choose` never loops.
  const triedRef = useRef(new Set<string>());
  const target = state.setupTool;
  const keptPage = state.setupPage;
  const asked = tools && target ? tools.find((tool) => tool.id === target) : undefined;
  const needsPick = asked !== undefined && !isChosen(asked);

  const screens = tools ? buildScreens(tools) : [];
  const index = tools ? openIndex(screens, tools, target, keptPage) : null;
  const openKey = index === null ? null : screenKey(screens[index]);
  const setIndex = (to: number) => dispatch({ type: "setupPage", page: screenKey(screens[to]) });

  useEffect(() => {
    // Keep the resumed page, so a later `setup list` (a step done) can't move the wizard.
    const keep = pageToKeep(openKey, keptPage, needsPick);
    if (keep !== null) dispatch({ type: "setupPage", page: keep });
  }, [openKey, keptPage, needsPick, dispatch]);

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

  return { screens, index, setIndex, pickError };
}

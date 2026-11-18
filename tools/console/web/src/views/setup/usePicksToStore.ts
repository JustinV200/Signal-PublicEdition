// Puts the picked tool ids from a `setup list` read into the store, where the
// console tour reads them (it skips the tabs of tools not picked). Both reads
// call it: the Setup tab's (at sign-in, on opening or closing Setup, on
// Refresh) and the wizard's own (after each pick), so a tour started right
// after picking already knows the new picks.
import { useEffect } from "react";
import type { SetupTool } from "../../api";
import { useStore } from "../../state";
import { isChosen } from "./wizardScreens";

/**
 * Stores `tools`' picks whenever a new list arrives.
 *
 * @param tools The last `setup list` answer; null before one (nothing is stored then).
 */
export function usePicksToStore(tools: readonly SetupTool[] | null): void {
  const { dispatch } = useStore();
  useEffect(() => {
    if (tools) dispatch({ type: "setupPicks", picks: tools.filter(isChosen).map((t) => t.id) });
  }, [tools, dispatch]);
}

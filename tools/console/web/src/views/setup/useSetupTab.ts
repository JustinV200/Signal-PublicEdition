// Whether the status line shows the Setup tab. The rule is wizardScreens'
// showsSetupTab; the picks come from `setup list` (read-only, so it never
// waits on a running step), read once at sign-in, again whenever Setup opens
// or closes (a tool may have finished there), and on the status line's Refresh.
// Each read also puts the picks in the store, for the console tour.
import { firstJson, parseTools } from "../../api";
import type { SetupRequest } from "../../api";
import { usePicksToStore } from "./usePicksToStore";
import { useSetupQuery } from "./useSetupQuery";
import { showsSetupTab } from "./wizardScreens";

const LIST_REQUEST: SetupRequest = { command: "list" };

/**
 * Reads the picks and applies the Setup tab rule.
 *
 * @param isSetupOpen Setup is the current view.
 * @returns True while the Setup tab should show.
 */
export function useSetupTab(isSetupOpen: boolean): boolean {
  // The key carries isSetupOpen, so opening or closing Setup re-reads the list.
  const list = useSetupQuery(`tab:${isSetupOpen}`, LIST_REQUEST, (lines) =>
    parseTools(firstJson(lines)),
  );
  usePicksToStore(list.data);
  return showsSetupTab(isSetupOpen, list.data);
}

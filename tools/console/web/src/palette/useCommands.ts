// Binds the Commands list to the store: the current state in, the store's
// dispatch and the buttons' confirm gate out, so palette actions ask exactly
// what the buttons ask.
import { useMemo } from "react";
import {
  currentTheme,
  isTodoAvailable,
  NIGHT_VIEW,
  setTheme,
  useConfirmGate,
  useStore,
} from "../state";
import { buildCommands } from "./commands";
import type { Command } from "./commands";
import { toggleAway } from "./toggleAway";

/**
 * The commands that apply now; empty while Commands is closed.
 *
 * @param isOpen Command mode is on. The list is built only then, so the theme (kept on the
 *   page, not in the store) is read afresh each time Commands opens.
 */
export function useCommands(isOpen: boolean): Command[] {
  const { state, dispatch } = useStore();
  const { request } = useConfirmGate();
  const { server, view } = state;
  return useMemo(() => {
    if (!isOpen) return [];
    return buildCommands({
      saves: server?.board.saves.map((save) => save.name) ?? [],
      todoAvailable: isTodoAvailable(server),
      nightView: server?.board.view === NIGHT_VIEW,
      voiceRunning: server?.voice.running ?? false,
      away: server?.away?.state ?? null,
      theme: currentTheme(),
      view,
      runAction: request,
      setView: (next) => dispatch({ type: "view", view: next }),
      setTheme,
      setAway: (isAway) => void toggleAway(isAway, dispatch),
      openHelp: () => dispatch({ type: "help", open: true }),
      refresh: () => dispatch({ type: "refresh" }),
    });
  }, [isOpen, server, view, request, dispatch]);
}

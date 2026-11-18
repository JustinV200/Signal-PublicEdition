// One running state for the whole setup wizard. The server runs one setup
// command that writes at a time (a second gets a 409), so the wizard runs one
// at a time too: the button that started it reads "Working…", and every other
// button is off with the quiet reason "another step is running" (a tooltip;
// the running log already says so). Each button has a key, so two buttons of
// one control (Yes / No) tell apart. Outside the wizard (System's tools
// list) each runner keeps its own state.
import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

/** Why a button is off while another one's command runs. */
export const ANOTHER_RUNNING = "another step is running";
/** The wizard header's line while any command runs (a disabled button can't be focused). */
export const RUNNING_NOTE = "a step is running: others wait";

/** What a button shows: Working… while its own command runs, off while another's does. */
export interface ButtonLook {
  pending: boolean;
  quietReason?: string;
}

/** Which button's command is running (a key), or null; and its setter. */
export interface RunningState {
  active: string | null;
  setActive: (update: (active: string | null) => string | null) => void;
}

const RunningContext = createContext<RunningState | null>(null);

/**
 * Claiming the running state for the button keyed `key`: it gets it only when it's
 * free (a run started without a click, such as the claim step's self-tick, must never
 * take it from another). Returns the new state.
 */
export function claim(active: string | null, key: string): string | null {
  return active ?? key;
}

/** Releasing it: only its holder frees it; anyone else's release changes nothing. */
export function release(active: string | null, key: string): string | null {
  return active === key ? null : active;
}

/** The look of the button keyed `key` while the button keyed `active` (or none) runs. */
export function buttonLook(active: string | null, key: string): ButtonLook {
  if (active === null) return { pending: false };
  return active === key ? { pending: true } : { pending: false, quietReason: ANOTHER_RUNNING };
}

/** Shares one running state with every runner below it (the wizard). */
export function RunningProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<string | null>(null);
  return (
    <RunningContext.Provider value={{ active, setActive }}>{children}</RunningContext.Provider>
  );
}

/** The wizard's shared running state, or (outside a RunningProvider) this runner's own. */
export function useRunningState(): RunningState {
  const shared = useContext(RunningContext);
  const [active, setActive] = useState<string | null>(null);
  return shared ?? { active, setActive };
}

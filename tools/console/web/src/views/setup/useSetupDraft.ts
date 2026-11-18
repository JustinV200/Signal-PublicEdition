// One wizard field's typed text, held in the store (`setupDrafts`) rather than
// in the field's component, so it is still there after the owner leaves Setup
// and comes back (the view unmounts on the way out).
import { useStore } from "../../state";

/**
 * The draft under `key` and its setter.
 *
 * @param key A key unique to the field, e.g. `value/mail/email`.
 * @returns The text ("" when nothing was typed) and a setter; null forgets the draft.
 */
export function useSetupDraft(key: string): [string, (text: string | null) => void] {
  const { state, dispatch } = useStore();
  const setText = (text: string | null) => dispatch({ type: "setupDraft", key, text });
  return [state.setupDrafts[key] ?? "", setText];
}

// Up/Down recall of sent messages. Recall only starts on an empty draft or
// an unedited recalled one; typing anything leaves recall until the next send.
import { useState } from "react";
import { pushHistory, readHistory } from "./history";

export interface HistoryRecall {
  /** Up: show the previous entry. Returns false when there is nothing to do. */
  recallOlder: () => boolean;
  /** Down: show the next entry, or an empty draft past the newest. */
  recallNewer: () => boolean;
  /** Record a sent message and reset the recall position. */
  remember: (text: string) => void;
}

/** Wires history recall to a draft and its setter. */
export function useHistoryRecall(draft: string, setDraft: (text: string) => void): HistoryRecall {
  const [entries, setEntries] = useState(readHistory);
  const [position, setPosition] = useState<number | null>(null);
  // The text we last put in the draft, so an untouched recall still counts as "empty".
  const [recalledText, setRecalledText] = useState<string | null>(null);
  const canRecall = draft === "" || draft === recalledText;

  const show = (index: number | null) => {
    const text = index === null ? "" : entries[index];
    setPosition(index);
    setRecalledText(text);
    setDraft(text);
  };

  return {
    recallOlder: () => {
      if (!canRecall || entries.length === 0) return false;
      show(position === null ? entries.length - 1 : Math.max(0, position - 1));
      return true;
    },
    recallNewer: () => {
      if (!canRecall || position === null) return false;
      show(position + 1 >= entries.length ? null : position + 1);
      return true;
    },
    remember: (text) => {
      setEntries(pushHistory(text));
      setPosition(null);
      setRecalledText(null);
    },
  };
}

// One view tab in the status line: a bordered box with the view's name, its
// live status words and the shortcut hint. The status text is keyed by
// `textKey`, so a change of state fades the new wording in; ticking numbers
// inside it keep the key.
import { useState } from "react";
import type { ReactNode } from "react";
import styles from "./status.module.css";

interface TabProps {
  /** The view's name, e.g. "Voice". */
  name: string;
  /** Keyboard shortcut shown as a hint, e.g. "Ctrl+2". */
  hint: string;
  active: boolean;
  onClick: () => void;
  /** Changes when the status wording changes (not on every clock tick). */
  textKey: string;
  children?: ReactNode;
}

/** A tab; the active one is filled, bordered brighter and bold, not just recoloured. */
export function Tab({ name, hint, active, onClick, textKey, children }: TabProps) {
  // Nothing fades on the first paint; only a later change of wording does.
  const [seenKey, setSeenKey] = useState(textKey);
  const [hasChanged, setHasChanged] = useState(false);
  if (seenKey !== textKey) {
    setSeenKey(textKey);
    setHasChanged(true);
  }
  return (
    <button
      type="button"
      role="tab"
      className={`${styles.tab} ${active ? styles.tabActive : ""}`}
      onClick={onClick}
      aria-selected={active}
    >
      <span className={styles.tabName}>{name}</span>
      {children && (
        <span key={textKey} className={`${styles.tabStatus} ${hasChanged ? "anim-fade" : ""}`}>
          {children}
        </span>
      )}
      <kbd className={styles.hint}>{hint}</kbd>
    </button>
  );
}

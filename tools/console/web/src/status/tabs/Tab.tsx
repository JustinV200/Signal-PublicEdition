// One view tab in the status line: a bordered box with the view's name and
// its live status words; the keyboard shortcut is the tooltip (Help lists
// them too), which keeps the tabs to one row. Only the active tab is in the
// Tab order (a roving tabindex: TabRow moves focus with the arrow keys). The
// status text is keyed by `textKey`, so a change of state fades the new
// wording in; ticking numbers inside it keep the key. The console tour's
// stop reads `◂ tour` after the words, so the bar and its tab line up.
import { useState } from "react";
import type { ReactNode } from "react";
import { Mark } from "../../ui";
import styles from "../status.module.css";

interface TabProps {
  /** The view's name, e.g. "Voice". */
  name: string;
  /** Keyboard shortcut, shown as the tab's tooltip, e.g. "Ctrl+2". */
  shortcut: string;
  active: boolean;
  onClick: () => void;
  /** Changes when the status wording changes (not on every clock tick). */
  textKey: string;
  /** The console tour's bar is showing this tab's stop: the tab reads `◂ tour`. */
  isTourStop?: boolean;
  children?: ReactNode;
}

/** A tab; the active one is filled, bordered brighter and bold, not just recoloured. */
export function Tab({
  name,
  shortcut,
  active,
  onClick,
  textKey,
  isTourStop = false,
  children,
}: TabProps) {
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
      tabIndex={active ? 0 : -1}
      title={shortcut}
    >
      <span className={styles.tabName}>{name}</span>
      {children && (
        <span key={textKey} className={`${styles.tabStatus} ${hasChanged ? "anim-fade" : ""}`}>
          {children}
        </span>
      )}
      {isTourStop && (
        <span className={styles.tourMark}>
          <span className={styles.pointLeft}>
            <Mark shape="triangle" />
          </span>{" "}
          tour
        </span>
      )}
    </button>
  );
}

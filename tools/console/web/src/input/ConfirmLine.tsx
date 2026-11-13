// Confirm mode: `stop the voice hub? [y/n]` in place of the textarea. It takes
// focus on mount; `y` confirms, `n` or Esc cancels (Esc is handled globally).
import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import styles from "./input.module.css";

interface ConfirmLineProps {
  prompt: string;
  onYes: () => void;
  onNo: () => void;
}

/** The y/n question line. */
export function ConfirmLine({ prompt, onYes, onNo }: ConfirmLineProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => ref.current?.focus(), []);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const key = event.key.toLowerCase();
    if (key === "y") onYes();
    else if (key === "n") onNo();
    else return;
    event.preventDefault();
  };

  return (
    <div
      ref={ref}
      tabIndex={0}
      role="alertdialog"
      aria-label={prompt}
      className={styles.confirm}
      onKeyDown={onKeyDown}
    >
      {prompt} <span className={styles.keys}>[y/n]</span>
    </div>
  );
}

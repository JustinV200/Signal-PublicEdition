// The command palette list. Presentational: the input line owns the query
// and the Up/Down/Enter keys (it is the combobox, pointing at the selected
// option with aria-activedescendant); clicking a row runs it. The list shows
// VISIBLE_ROWS rows and scrolls, keeping the selected row in view, and a last
// line says how many more matched, so a long list never hides that it goes on.
import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { Mark } from "../ui";
import type { Command } from "./commands";
import styles from "./palette.module.css";

/** The list's height in rows, passed to its CSS max-height as `--rows`. */
export const VISIBLE_ROWS = 8;
/** The listbox's id, for the input's aria-controls. */
export const PALETTE_LIST_ID = "palette-list";

/** The id of option `index`, for the input's aria-activedescendant. */
export function paletteOptionId(index: number): string {
  return `palette-option-${index}`;
}

interface PaletteProps {
  matches: readonly Command[];
  selectedIndex: number;
  onPick: (command: Command) => void;
}

/** Matches above the input line; `▸` marks the one Enter will run. */
export function Palette({ matches, selectedIndex, onPick }: PaletteProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const hiddenCount = matches.length - VISIBLE_ROWS;

  // Up/Down past the visible rows scrolls the list just enough to show the selected one.
  useEffect(() => {
    const option = listRef.current?.querySelector(`#${paletteOptionId(selectedIndex)}`);
    option?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex, matches]);

  return (
    <div className={`frame ${styles.panel} anim-pop`}>
      <div
        ref={listRef}
        id={PALETTE_LIST_ID}
        className={styles.list}
        style={{ "--rows": VISIBLE_ROWS } as CSSProperties}
        role="listbox"
        aria-label="commands"
      >
        {matches.length === 0 && <div className={styles.none}>no matching command</div>}
        {matches.map((command, index) => {
          const selected = index === selectedIndex;
          return (
            <button
              key={command.label}
              id={paletteOptionId(index)}
              type="button"
              role="option"
              aria-selected={selected}
              tabIndex={-1}
              className={`${styles.item} ${selected ? styles.selected : ""}`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onPick(command)}
            >
              <span className={styles.mark} aria-hidden="true">
                {selected && <Mark shape="triangle" />}
              </span>
              {command.label}
            </button>
          );
        })}
      </div>
      {hiddenCount > 0 && <div className={styles.more}>+ {hiddenCount} more: keep typing</div>}
    </div>
  );
}

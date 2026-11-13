// The command palette list. Presentational: the input line owns the query
// and the Up/Down/Enter keys; clicking a row runs it.
import type { Command } from "./commands";
import styles from "./palette.module.css";

interface PaletteProps {
  matches: readonly Command[];
  selectedIndex: number;
  onPick: (command: Command) => void;
}

const SELECTED_MARK = "▸";

/** Matches above the input line; `▸` marks the one Enter will run. */
export function Palette({ matches, selectedIndex, onPick }: PaletteProps) {
  return (
    <div className={`col ${styles.list} anim-pop`} role="listbox" aria-label="commands">
      {matches.length === 0 && <div className={styles.none}>no matching command</div>}
      {matches.map((command, index) => {
        const selected = index === selectedIndex;
        return (
          <button
            key={command.label}
            type="button"
            role="option"
            aria-selected={selected}
            tabIndex={-1}
            className={`${styles.item} ${selected ? styles.selected : ""}`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onPick(command)}
          >
            <span className={styles.mark} aria-hidden="true">
              {selected ? SELECTED_MARK : ""}
            </span>
            {command.label}
          </button>
        );
      })}
    </div>
  );
}

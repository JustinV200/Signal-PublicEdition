// One board in the list: `▸` when selected, name, `saved <relative>` and a
// bold "Showing" tag when it is on the projector. Click or focus selects it
// and nothing more; the preview's button does the loading.
import styles from "./boards.module.css";

interface BoardRowProps {
  name: string;
  meta: string;
  selected: boolean;
  showing: boolean;
  onSelect: () => void;
}

const SELECTED_MARK = "▸";

/** A selectable row (roving tabindex: only the selected row is tabbable). */
export function BoardRow({ name, meta, selected, showing, onSelect }: BoardRowProps) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      tabIndex={selected ? 0 : -1}
      className={`${styles.row} ${selected ? styles.selected : ""}`}
      onClick={onSelect}
      onFocus={onSelect}
    >
      <span className={styles.mark} aria-hidden="true">
        {selected ? SELECTED_MARK : ""}
      </span>
      <span className={styles.name}>{name}</span>
      <span className={styles.meta}>{meta}</span>
      <span className={styles.tag}>{showing ? "Showing" : ""}</span>
    </button>
  );
}

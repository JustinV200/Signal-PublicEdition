// The `↓ N new` pill that sticks to the bottom of a log while unread rows sit below.
import styles from "./scroll.module.css";

/** Renders nothing when `count` is 0. */
export function NewPill({ count, onClick }: { count: number; onClick: () => void }) {
  if (count === 0) return null;
  return (
    <button type="button" className={`${styles.pill} anim-fade`} onClick={onClick}>
      ↓ {count} new
    </button>
  );
}

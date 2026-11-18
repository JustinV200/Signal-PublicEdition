// The `↓ N new` pill that sticks to the bottom of a log while unread rows sit
// below: ui's Button, on a sticky strip that lets clicks through around it.
import { Button } from "../ui";
import styles from "./scroll.module.css";

/** Renders nothing when `count` is 0. */
export function NewPill({ count, onClick }: { count: number; onClick: () => void }) {
  if (count === 0) return null;
  return (
    <div className={`${styles.pill} anim-fade`}>
      <Button onClick={onClick}>↓ {count} new</Button>
    </div>
  );
}

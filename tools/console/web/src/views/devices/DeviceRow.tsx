// One device: a shape (ui's disc on, ring off, `?` unknown), its name
// and the server's words, which always carry the state (no separate state
// word, so nothing is said twice). A row that isn't on sets its words in 600;
// the shape is the second cue and colour only a third, so it also works for
// colourblind users. The webcam row also gets the Open camera button.
import type { ReactNode } from "react";
import type { DeviceRow as Device } from "../../api";
import { Mark } from "../../ui";
import styles from "./devices.module.css";

// `?` is plain text: Plex has it, and no shape says "unknown".
const MARKS: Record<Device["state"], ReactNode> = {
  on: <Mark shape="disc" />,
  off: <Mark shape="ring" />,
  unknown: "?",
};

interface DeviceRowProps {
  device: Device;
  /** The row's action, e.g. the webcam's Open camera button. */
  children?: ReactNode;
}

/** A device row in the list. */
export function DeviceRow({ device, children }: DeviceRowProps) {
  return (
    <li className={styles.row}>
      <span className={`${styles.mark} ${styles[device.state] ?? ""}`} aria-hidden="true">
        {MARKS[device.state]}
      </span>
      <span className={styles.name}>{device.name}</span>
      <span className={device.state === "on" ? styles.words : `${styles.words} ${styles.notOk}`}>
        {device.words}
      </span>
      <span className={styles.action}>{children}</span>
    </li>
  );
}

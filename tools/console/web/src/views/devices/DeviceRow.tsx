// One device: a shape (filled dot on, hollow dot off, `?` unknown), its name
// and its state in words. The words always carry the state; the shape is the
// second cue and colour only a third (the owner is colourblind). The webcam row
// also gets the Open camera button.
import type { ReactNode } from "react";
import type { DeviceRow as Device } from "../../api";
import styles from "./devices.module.css";

const MARKS: Record<Device["state"], string> = { on: "●", off: "○", unknown: "?" };
const STATE_WORDS: Record<Device["state"], string> = {
  on: "on",
  off: "off",
  unknown: "unknown",
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
      <span className={styles.words}>
        <span className={styles.stateWord}>{STATE_WORDS[device.state]}</span> {device.words}
      </span>
      <span className={styles.action}>{children}</span>
    </li>
  );
}

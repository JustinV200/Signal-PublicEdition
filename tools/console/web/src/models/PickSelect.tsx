// One model or effort picker: a native select over the server's fixed list.
// Choosing an option sends its index, never its text. While the current
// value isn't in the list (unset for voice, or a hand-edited settings value),
// or can't be known (an unreadable settings file), a disabled placeholder
// option names it. A pick sends focus back to the input line.
import type { ModelTarget } from "../api";
import { focusInput } from "../input";
import styles from "./models.module.css";
import { offListLabel, optionLabel } from "./modelWords";

interface PickSelectProps {
  /** For the visible `<label htmlFor>` beside it. */
  id: string;
  target: ModelTarget;
  /** Accessible name, e.g. "Voice effort" (it contains the visible label's word). */
  label: string;
  options: (string | null)[];
  current: string | null;
  onPick: (index: number) => void;
  /** Set, it disables the picker and becomes its tooltip. */
  disabledReason?: string;
  /** Set when the current value can't be known: shown as the placeholder whatever `current` is. */
  unknownLabel?: string;
}

const OFF_LIST = "off-list";

/** A labelled select; the parent decides what a pick does. */
export function PickSelect({
  id,
  target,
  label,
  options,
  current,
  onPick,
  disabledReason,
  unknownLabel,
}: PickSelectProps) {
  const index = unknownLabel ? -1 : options.indexOf(current);
  return (
    <select
      id={id}
      className={styles.select}
      aria-label={label}
      title={disabledReason ?? label}
      disabled={Boolean(disabledReason)}
      value={index < 0 ? OFF_LIST : String(index)}
      onChange={(event) => {
        onPick(Number(event.target.value));
        // Off the picker, so a letter typed next goes to the input, not the select's type-ahead.
        focusInput();
      }}
    >
      {index < 0 && (
        <option value={OFF_LIST} disabled>
          {unknownLabel ?? offListLabel(target, current)}
        </option>
      )}
      {options.map((value, position) => (
        <option key={position} value={String(position)}>
          {optionLabel(value)}
        </option>
      ))}
    </select>
  );
}

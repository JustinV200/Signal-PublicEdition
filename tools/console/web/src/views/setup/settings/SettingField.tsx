// One setting as a form field: its description, the input its type maps to
// (fields.ts), the hint, and a "placeholder: replace it" marker in words and
// a `!` mark (never colour alone) while the saved value is still a shipped
// placeholder.
import type { SettingRow } from "../../../api";
import styles from "../setup.module.css";
import { fieldHint, fieldKind } from "./fields";

interface SettingFieldProps {
  row: SettingRow;
  draft: string;
  onChange: (text: string) => void;
}

/** A labelled input for one setting. */
export function SettingField({ row, draft, onChange }: SettingFieldProps) {
  const kind = fieldKind(row.type);
  const inputId = `setting-${row.id}`;
  const hint = fieldHint(row);
  return (
    <div className={styles.field}>
      <label htmlFor={inputId} className={styles.fieldLabel}>
        {row.isPlaceholder && <span className={styles.flag}>! placeholder: replace it · </span>}
        {row.description || row.id}
      </label>
      {kind === "checkbox" ? (
        <label className={styles.check}>
          <input
            id={inputId}
            type="checkbox"
            checked={draft === "yes"}
            onChange={(event) => onChange(event.target.checked ? "yes" : "no")}
          />
          {draft === "yes" ? "yes" : "no"}
        </label>
      ) : (
        <input
          id={inputId}
          className={styles.input}
          type={kind}
          step={row.type === "float" ? "any" : undefined}
          min={row.min ?? undefined}
          max={row.max ?? undefined}
          value={draft}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      <span className={styles.fieldHint}>
        {row.id !== row.description && <code>{row.id}</code>} {hint}
      </span>
    </div>
  );
}

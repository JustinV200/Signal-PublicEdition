// A settings step as a form, rendered from the tool's schema
// (tools/setup data/settings/<tool>.json through `setup config <tool> --list`).
// "Open settings" runs the step (it copies the config files from their
// examples, keeping any you have), then lists the step's settings: basic ones
// and any placeholder left first, advanced ones behind a toggle. Save sends
// only the changed values (`setup config <tool> --set`); the CLI checks them,
// re-runs a step a change affects (e.g. a scheduled task) and marks the step
// done once no placeholder is left. What the owner types is kept in the
// store (`setupDrafts`), so after leaving Setup and coming back the form
// reopens by itself with the typed values still in it.
import { useEffect, useRef, useState } from "react";
import { firstJson, parseSettings } from "../../../api";
import type { SettingRow, SetupStep } from "../../../api";
import { useStore } from "../../../state";
import { Button, Mark } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import styles from "../setup.module.css";
import { changedValues, valueText } from "./fields";
import { SettingField } from "./SettingField";

interface SettingsFormProps {
  toolId: string;
  step: SetupStep;
  /** Called after a save, so the step's status is read again. */
  onSaved: () => void;
}

interface SaveReply {
  errors?: Record<string, string>;
  placeholders_left?: string[];
}

/** The form for one settings step. */
export function SettingsForm({ toolId, step, onSaved }: SettingsFormProps) {
  const { state, dispatch } = useStore();
  const opener = useSetupRun();
  const saver = useSetupRun();
  const [rows, setRows] = useState<SettingRow[] | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [reply, setReply] = useState<SaveReply | null>(null);
  // Typed values live in the store under this step's prefix, so they outlast leaving Setup.
  const prefix = `settings/${toolId}/${step.id}/`;
  const typed = state.setupDrafts;
  const drafts = Object.fromEntries(
    (rows ?? []).map((r) => [r.id, typed[prefix + r.id] ?? valueText(r.value, r.type)]),
  );
  const setDraft = (id: string, text: string | null) =>
    dispatch({ type: "setupDraft", key: prefix + id, text });
  // Typed before the owner left Setup: the form opens again by itself to show them.
  const hadTypedRef = useRef(Object.keys(typed).some((key) => key.startsWith(prefix)));

  const load = async () => {
    const listed = await opener.run({ command: "config", tool: toolId });
    if (!listed || listed.exit !== 0) return;
    setRows(parseSettings(firstJson(listed.lines)).filter((r) => r.group === step.group));
  };
  useEffect(() => {
    if (hadTypedRef.current) void load();
    // Once, on mount: `load` is a fresh function each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const open = async () => {
    const created = await opener.run({ command: "apply", tool: toolId, step: step.id });
    // Exit 3 just means placeholders are left to fill in: that's what the form is for.
    if (created && (created.exit === 0 || created.exit === 3)) await load();
  };
  const save = async () => {
    if (!rows) return;
    const changed = changedValues(rows, drafts);
    if (Object.keys(changed).length === 0) return;
    const result = await saver.run({ command: "config", tool: toolId, set: changed });
    if (!result) return;
    const saved = firstJson(result.lines) as SaveReply;
    setReply(saved);
    // A saved value shows as the CLI stored it; a refused one keeps what was typed.
    for (const id of Object.keys(changed)) if (!saved.errors?.[id]) setDraft(id, null);
    await load();
    onSaved();
  };

  if (!rows) {
    return (
      <div className={styles.controls}>
        <Button onClick={() => void open()} {...opener.button()}>
          Open settings
        </Button>
        <OutputLog run={opener} what={`${toolId}: ${step.title}`} />
      </div>
    );
  }
  const shown = rows.filter((r) => r.level === "basic" || r.isPlaceholder || showAdvanced);
  const hidden = rows.length - shown.length;
  const unsaved = Object.keys(changedValues(rows, drafts)).length;
  return (
    <div className={styles.form}>
      {shown.map((row) => (
        <SettingField
          key={row.id}
          row={row}
          draft={drafts[row.id] ?? ""}
          onChange={(text) => setDraft(row.id, text)}
        />
      ))}
      <div className={styles.controls}>
        <Button
          primary
          onClick={() => void save()}
          {...saver.button()}
          disabledReason={unsaved === 0 ? "nothing changed" : undefined}
        >
          Save settings
        </Button>
        {(hidden > 0 || showAdvanced) && (
          <Button onClick={() => setShowAdvanced(!showAdvanced)} expanded={showAdvanced}>
            {showAdvanced ? "Hide advanced" : `Show ${hidden} advanced`}
          </Button>
        )}
      </div>
      <SaveSummary reply={reply} />
      <OutputLog run={saver} what={`${toolId}: ${step.title}`} />
    </div>
  );
}

/** What the last save did, in words: refused values and placeholders still left. */
function SaveSummary({ reply }: { reply: SaveReply | null }) {
  if (!reply) return null;
  const errors = Object.entries(reply.errors ?? {});
  const left = reply.placeholders_left ?? [];
  return (
    <ul className={styles.summary} role="status">
      {errors.map(([id, why]) => (
        <li key={id}>
          <Mark shape="cross" /> {id}: {why}
        </li>
      ))}
      <li>
        {left.length ? (
          `! placeholders left: ${left.join(", ")}`
        ) : (
          <>
            <Mark shape="check" /> no placeholders left
          </>
        )}
      </li>
    </ul>
  );
}

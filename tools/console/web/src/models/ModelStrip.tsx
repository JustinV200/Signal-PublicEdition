// The model strip, on the Models page (ModelsView). Two rows:
//   ORCHESTRATOR  now: opus-5-5 · medium  next session [model] [effort]  applies to...
//   VOICE         [model] [effort]  applies on your next request
// then a hint on switching the running session from VS Code.
// Like the Away/Here toggle, a pick acts directly (POST /api/models) on
// the owner's click instead of asking Claude. The new state comes back on the
// event stream, so the pickers always show what the server holds.
import { useState } from "react";
import { pickModel, UnauthorizedError } from "../api";
import type { ModelField, ModelPick, ModelsState, ModelTarget } from "../api";
import { useStore } from "../state";
import styles from "./models.module.css";
import {
  NEXT_SESSION_NOTE,
  nowWords,
  SWITCH_NOW_HINT,
  UNREADABLE_LABEL,
  UNREADABLE_REASON,
  VOICE_NOTE,
} from "./modelWords";
import { PickSelect } from "./PickSelect";

const SAVING_REASON = "saving the last pick";
const FIELDS: ModelField[] = ["model", "effort"];
const NO_PICK: ModelPick = { model: null, effort: null };

interface PickersProps {
  models: ModelsState;
  target: ModelTarget;
  current: ModelPick | null;
  onPick: (target: ModelTarget, field: ModelField, index: number) => void;
  disabledReason?: string;
  /** Shown in both pickers instead of a value that can't be known. */
  unknownLabel?: string;
}

/** The model and effort pickers for one target. */
function Pickers({ models, target, current, onPick, disabledReason, unknownLabel }: PickersProps) {
  return (
    <>
      {FIELDS.map((field) => (
        <PickSelect
          key={field}
          target={target}
          label={`${target} ${field}`}
          options={models.choices[target][field]}
          current={(current ?? NO_PICK)[field]}
          onPick={(index) => onPick(target, field, index)}
          disabledReason={disabledReason}
          unknownLabel={unknownLabel}
        />
      ))}
    </>
  );
}

/** The strip; renders nothing until the server reports its models block. */
export function ModelStrip() {
  const { state, dispatch } = useStore();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const models = state.server?.models;
  if (!models) return null;

  const onPick = async (target: ModelTarget, field: ModelField, index: number) => {
    setBusy(true);
    setProblem(null);
    try {
      await pickModel(target, field, index);
    } catch (failure) {
      if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
      setProblem(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };
  const pick = (target: ModelTarget, field: ModelField, index: number) =>
    void onPick(target, field, index);
  const { next } = models.orchestrator;
  const savingReason = busy ? SAVING_REASON : undefined;

  return (
    <div className={styles.strip}>
      <div className={styles.row}>
        <span className={`hud-label ${styles.key}`}>Orchestrator</span>
        <span className={styles.now}>{nowWords(models.orchestrator.now)}</span>
        <span className={styles.label}>next session</span>
        <Pickers
          models={models}
          target="orchestrator"
          current={next}
          onPick={pick}
          disabledReason={next ? savingReason : UNREADABLE_REASON}
          unknownLabel={next ? undefined : UNREADABLE_LABEL}
        />
        <span className={styles.note}>{NEXT_SESSION_NOTE}</span>
      </div>
      <div className={styles.row}>
        <span className={`hud-label ${styles.key}`}>Voice</span>
        <Pickers
          models={models}
          target="voice"
          current={models.voice}
          onPick={pick}
          disabledReason={savingReason}
        />
        <span className={styles.note}>{VOICE_NOTE}</span>
      </div>
      <p className={styles.hint}>{SWITCH_NOW_HINT}</p>
      {problem && <p className={styles.problem}>{problem}</p>}
    </div>
  );
}

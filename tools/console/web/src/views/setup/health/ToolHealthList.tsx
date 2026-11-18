// The tools' health list (System's TOOLS group and the wizard's summary):
// HealthList's rows with each tool's button. A finished tool not in Claude
// Code's config yet gets Add to Claude Code (the caller runs `setup wire` and
// shows what happened); every other row's button opens the setup wizard at
// that tool, and a Fix carries the failing check along, so the tool page
// leads with why it was opened. Every Add runs the same wire, so only the
// row clicked reads "Working…".
import { useState } from "react";
import type { ToolHealth } from "../../../api";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import { ANOTHER_RUNNING } from "../run";
import type { ButtonLook } from "../run";
import { HealthList } from "./HealthList";
import { healthAction, shownHealth, toolItem } from "./healthWords";

const NOT_HERE = "can't run on this OS";

interface ToolHealthListProps {
  rows: readonly ToolHealth[];
  /** Adds the finished tools to Claude Code. */
  onAdd: () => void;
  /** The add runner's button look (Working… while it runs, off while another runs). */
  addButton: ButtonLook;
}

/** One row per tool, with its button. */
export function ToolHealthList({ rows, onAdd, addButton }: ToolHealthListProps) {
  const { dispatch } = useStore();
  const [clicked, setClicked] = useState<string | null>(null);
  const byKey = new Map(rows.map((row) => [toolItem(row).key, row]));
  // While the add runs, the clicked row reads Working… and the other Add rows are off.
  const addLook = (id: string): ButtonLook =>
    addButton.pending
      ? { pending: clicked === id, quietReason: clicked === id ? undefined : ANOTHER_RUNNING }
      : addButton;
  const add = (id: string) => {
    setClicked(id);
    onAdd();
  };
  const openSetup = (row: ToolHealth) =>
    // Only a Down row carries its check: the tool page then says why every step reads done.
    dispatch({ type: "openSetup", tool: row.id, check: row.state === "down" ? row : undefined });

  return (
    <HealthList
      items={rows.map(toolItem)}
      renderAction={(item) => {
        const row = byKey.get(item.key);
        if (!row) return null;
        const isAdd = shownHealth(row) === "not_wired";
        return (
          <Button
            primary={isAdd}
            {...(isAdd ? addLook(row.id) : {})}
            onClick={isAdd ? () => add(row.id) : () => openSetup(row)}
            disabledReason={row.supportedHere ? undefined : NOT_HERE}
          >
            {healthAction(row)}
          </Button>
        );
      }}
    />
  );
}

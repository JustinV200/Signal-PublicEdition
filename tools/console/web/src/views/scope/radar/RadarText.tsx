// One line of text on the radar at its placed position, in --font-small with
// a halo in the page colour (radar.module.css's .text), so lines and the sweep
// never run through the letters. Text on the face also sits on a plate in the
// page colour, since the halo hugs each glyph and a line could still run
// through the gaps between words (the crosshair through `CLAUDE · idle`).
// Its look says what it is.
import { boxOf } from "./labels";
import type { PlacedText } from "./labels";
import styles from "./radar.module.css";

/** A blip's label (`urgent`: bold, waits on the owner), a ring caption, a sector name or the NO SIGNAL banner. */
export type TextLook = "label" | "urgent" | "caption" | "sector" | "signal";

const LOOK_CLASSES: Record<TextLook, string> = {
  label: styles.label,
  urgent: `${styles.label} ${styles.urgent}`,
  caption: styles.caption,
  sector: styles.sectorName,
  signal: styles.signal,
};

// Sector names sit outside the rim, on the page itself: no plate.
const UNPLATED: ReadonlySet<TextLook> = new Set(["sector"]);

interface RadarTextProps {
  placed: PlacedText;
  look: TextLook;
  onClick?: () => void;
}

/** A positioned SVG text, on its plate when it is on the face. */
export function RadarText({ placed, look, onClick }: RadarTextProps) {
  const plate = UNPLATED.has(look) ? null : boxOf(placed);
  return (
    <g onClick={onClick} className={onClick ? styles.clickable : undefined}>
      {plate && (
        <rect
          className={styles.plate}
          x={plate.x0}
          y={plate.y0}
          width={plate.x1 - plate.x0}
          height={plate.y1 - plate.y0}
        />
      )}
      <text
        className={`${styles.text} ${LOOK_CLASSES[look]}`}
        x={placed.x}
        y={placed.y}
        textAnchor={placed.anchor}
      >
        {placed.text}
      </text>
    </g>
  );
}

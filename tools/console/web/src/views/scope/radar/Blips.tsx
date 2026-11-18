// The blips: every label first (each with a halo in the page colour, so the
// grid never runs through its letters), then every mark on top, so a label
// never hides a mark. Only the mark glows and pulses; a label stays still and
// plain. A click on a mark or its label opens the blip's view; the readout
// rows open the same views by keyboard, so the marks stay out of the tab order.
import type { View } from "../../../state";
import { MarkPath } from "../../../ui";
import type { PlacedText } from "./labels";
import { polar } from "./geometry";
import { RadarText } from "./RadarText";
import styles from "./radar.module.css";
import type { Blip } from "./types";

// The width of a blip's mark, in viewBox units, and the radius a click finds it in.
const BLIP_SIZE = 11;
const HIT_RADIUS = 10;
const PULSE_CLASSES: Record<NonNullable<Blip["pulse"]>, string> = {
  normal: "anim-pulse",
  slow: "anim-pulse-slow",
};

interface BlipsProps {
  blips: readonly Blip[];
  /** The labels that show, by blip id (labels.ts); a blip missing here shows only its mark. */
  labels: ReadonlyMap<string, PlacedText>;
  onOpen: (view: View) => void;
}

function BlipMark({ blip, onOpen }: { blip: Blip; onOpen: (view: View) => void }) {
  const at = polar(blip.bearingDeg, blip.range);
  const markClass = [
    styles.mark,
    blip.isUrgent ? styles.urgentMark : "",
    blip.pulse ? PULSE_CLASSES[blip.pulse] : "",
  ];
  return (
    <g className={markClass.join(" ")} onClick={() => onOpen(blip.view)}>
      {/* The full words on hover, for a label that is cut or hidden. */}
      <title>{`${blip.label}${blip.tail ?? ""}`}</title>
      <circle className={styles.hit} cx={at.x} cy={at.y} r={HIT_RADIUS} />
      <MarkPath shape={blip.shape} x={at.x} y={at.y} size={BLIP_SIZE} />
    </g>
  );
}

/** The labels, then the marks. */
export function Blips({ blips, labels, onOpen }: BlipsProps) {
  return (
    <>
      <g>
        {blips.map((blip) => {
          const placed = labels.get(blip.id);
          if (!placed) return null;
          return (
            <RadarText
              key={blip.id}
              placed={placed}
              look={blip.isUrgent ? "urgent" : "label"}
              onClick={() => onOpen(blip.view)}
            />
          );
        })}
      </g>
      <g className={styles.marks}>
        {blips.map((blip) => (
          <BlipMark key={blip.id} blip={blip} onOpen={onOpen} />
        ))}
      </g>
    </>
  );
}

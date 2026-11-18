// The radar scope: one SVG, 400 units drawn at 400px. The face and grid, the
// sweep, the fixed words (ring captions, sector names, `NO SIGNAL 25s` while
// the stream is stale), then the blips from blips.ts with the labels
// radar/labels.ts lays out. The sweep only runs while `sweeping` and stops
// under prefers-reduced-motion.
import type { View } from "../../state";
import {
  Blips,
  boxOf,
  Grid,
  layoutLabels,
  RadarText,
  ringCaptions,
  sectorNames,
  signalCaption,
  SIZE,
  Sweep,
} from "./radar";
import type { Blip } from "./radar";
import styles from "./scope.module.css";

interface ScopeProps {
  blips: Blip[];
  /** `NO SIGNAL 25s` while the stream is stale, else null. */
  signal: string | null;
  sweeping: boolean;
  onOpen: (view: View) => void;
}

/** The scope; the readout beside it carries the same facts as text. */
export function Scope({ blips, signal, sweeping, onOpen }: ScopeProps) {
  const captions = ringCaptions();
  const banner = signal ? signalCaption(signal) : null;
  // No label may cover a caption or the banner; sector names sit outside the rim.
  const fixed = [...captions, ...(banner ? [banner] : [])].map(boxOf);
  const labels = layoutLabels(blips, fixed);
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className={styles.scope} aria-hidden="true">
      <Grid />
      <Sweep sweeping={sweeping} />
      {captions.map((placed) => (
        <RadarText key={placed.text} placed={placed} look="caption" />
      ))}
      {sectorNames().map((placed) => (
        <RadarText key={placed.text} placed={placed} look="sector" />
      ))}
      <Blips blips={blips} labels={labels} onOpen={onOpen} />
      {banner && <RadarText placed={banner} look="signal" />}
    </svg>
  );
}

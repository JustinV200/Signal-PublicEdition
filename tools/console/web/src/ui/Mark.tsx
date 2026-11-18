// The console's state shapes (disc, ring, dashed ring, half, square, diamond,
// triangle, cross, check) drawn as SVG in currentColor. The bundled Plex subset
// has none of ● ○ ◐ ▸ ✗ ✓, so as text they fell back to other fonts; drawn,
// they look the same everywhere. `Mark` sits inline in text; `MarkPath`
// draws the same shape inside another SVG (the scope's blips). A shape is
// always a second cue: the words beside it carry the state, so marks are
// hidden from screen readers.
import styles from "./mark.module.css";

export type MarkShape =
  "disc" | "ring" | "dashedRing" | "half" | "square" | "diamond" | "triangle" | "cross" | "check";

// Shapes are drawn on a box of BOX units centred on 0, sized to look alike.
const BOX = 11;
const DISC_R = 4.5;
const RING_R = 3.75;
const STROKE = 1.5;
const SQUARE_HALF = 4;
const DIAMOND_HALF = 5.2;
const CROSS_HALF = 3.5;
// ▸: points right, like the selected-row cursor it replaces.
const TRIANGLE_POINTS = "-3.5,-4.5 4.5,0 -3.5,4.5";
// ✓: a short stroke down, then a long one up to the right.
const CHECK_POINTS = "-4,0.5 -1.5,3.5 4.5,-3.5";
// The dashed ring (nothing here yet): its path counted as DASH_UNITS long, so
// "1 1" gives DASH_UNITS / 2 even dashes whatever the radius.
const DASH_UNITS = 16;

/** The bare shape in BOX units around 0, coloured by `currentColor`. */
function ShapeBody({ shape }: { shape: MarkShape }) {
  const outline = { fill: "none", stroke: "currentColor", strokeWidth: STROKE };
  switch (shape) {
    case "disc":
      return <circle r={DISC_R} fill="currentColor" />;
    case "ring":
      return <circle r={RING_R} {...outline} />;
    case "dashedRing":
      return <circle r={RING_R} {...outline} pathLength={DASH_UNITS} strokeDasharray="1 1" />;
    case "half":
      // ◐: a ring with its left half filled.
      return (
        <>
          <circle r={RING_R} {...outline} />
          <path d={`M0 ${-RING_R} A${RING_R} ${RING_R} 0 0 0 0 ${RING_R} Z`} fill="currentColor" />
        </>
      );
    case "square":
      return (
        <rect
          x={-SQUARE_HALF}
          y={-SQUARE_HALF}
          width={SQUARE_HALF * 2}
          height={SQUARE_HALF * 2}
          fill="currentColor"
        />
      );
    case "diamond":
      return (
        <polygon
          points={`0,${-DIAMOND_HALF} ${DIAMOND_HALF},0 0,${DIAMOND_HALF} ${-DIAMOND_HALF},0`}
          fill="currentColor"
        />
      );
    case "triangle":
      return <polygon points={TRIANGLE_POINTS} fill="currentColor" />;
    case "cross":
      return (
        <path
          d={`M${-CROSS_HALF} ${-CROSS_HALF}L${CROSS_HALF} ${CROSS_HALF}M${CROSS_HALF} ${-CROSS_HALF}L${-CROSS_HALF} ${CROSS_HALF}`}
          {...outline}
          strokeLinecap="round"
        />
      );
    case "check":
      return (
        <polyline points={CHECK_POINTS} {...outline} strokeLinecap="round" strokeLinejoin="round" />
      );
  }
}

/** An inline mark, about the size of a lowercase letter, in the text's colour. */
export function Mark({ shape }: { shape: MarkShape }) {
  const half = BOX / 2;
  return (
    <svg
      className={styles.mark}
      viewBox={`${-half} ${-half} ${BOX} ${BOX}`}
      aria-hidden="true"
      focusable="false"
    >
      <ShapeBody shape={shape} />
    </svg>
  );
}

interface MarkPathProps {
  shape: MarkShape;
  /** Centre, in the parent SVG's units. */
  x: number;
  y: number;
  /** Width of the shape's box, in the parent SVG's units. */
  size: number;
}

/** The same shape drawn into a parent SVG at (x, y), `size` units across. */
export function MarkPath({ shape, x, y, size }: MarkPathProps) {
  return (
    <g transform={`translate(${x} ${y}) scale(${size / BOX})`}>
      <ShapeBody shape={shape} />
    </g>
  );
}

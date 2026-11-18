// The radar's coordinate system, shared by the drawing and the label layout:
// a fixed 400-unit viewBox drawn at 400px, so one unit is one pixel and text
// never scales. Bearings are degrees clockwise from the top; range is 0 at
// the centre and 1 on the rim.

export const SIZE = 400;
export const CENTER = SIZE / 2;
export const RADIUS = 184;

export interface Point {
  x: number;
  y: number;
}

/** The point at `bearingDeg` and `range` (a fraction of RADIUS). */
export function polar(bearingDeg: number, range: number): Point {
  const radians = ((bearingDeg - 90) * Math.PI) / 180;
  return {
    x: CENTER + Math.cos(radians) * RADIUS * range,
    y: CENTER + Math.sin(radians) * RADIUS * range,
  };
}

/** A pie slice from the centre to the rim, clockwise from `fromDeg` to `toDeg`. */
export function sectorPath(fromDeg: number, toDeg: number): string {
  const from = polar(fromDeg, 1);
  const to = polar(toDeg, 1);
  return `M ${CENTER} ${CENTER} L ${from.x} ${from.y} A ${RADIUS} ${RADIUS} 0 0 1 ${to.x} ${to.y} Z`;
}

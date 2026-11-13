// Planets (effects/): one or two steady bright points that never twinkle, an amber one
// and a warm white one, turning with the sky and placed where they stay on the board
// all night.

import { safeRadius, skyToCanvas } from "../../geometry.js";
import { fillDot, fillHalo } from "../../paint.js";
import { between } from "../../random.js";

const COUNT = [1, 2];
const PLACE = [0.3, 1]; // of the safe radius about the pivot (geometry.js)
const COLOURS = [[1, 0.62, 0.3], [1, 0.9, 0.72]]; // amber (Mars), warm white (Jupiter)
const RADIUS_PX = 3.2; // at 1080p
const HALO_RADIUS = 5; // of the planet's radius
const HALO_ALPHA = 0.45;

export default {
  name: "planets",
  family: "planets",
  build(next, sky) {
    const count = Math.round(between(next, ...COUNT));
    const reach = safeRadius(sky);
    const planets = [];
    for (let i = 0; i < count; i++) {
      const distance = between(next, ...PLACE) * reach;
      const angle = next() * 2 * Math.PI;
      planets.push({
        x: distance * Math.cos(angle),
        y: distance * Math.sin(angle),
        rgb: COLOURS[i % COLOURS.length],
      });
    }
    return { planets };
  },
  draw(context, state, frame) {
    const radius = RADIUS_PX * frame.px;
    for (const planet of state.planets) {
      const { x, y } = skyToCanvas(planet.x, planet.y, frame);
      fillHalo(context, x, y, radius * HALO_RADIUS, planet.rgb, HALO_ALPHA);
      fillDot(context, x, y, radius, planet.rgb, 1);
    }
  },
};

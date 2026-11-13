// Galaxies (effects/): two or three small tilted smudges turning with the sky, placed
// where they stay on the board all night, each slowly resolving from a faint haze into
// a brighter core and fading back over about twenty minutes. Drawn behind the stars.

import { safeRadius, skyToCanvas } from "../../geometry.js";
import { fillSoftDisk } from "../../paint.js";
import { between, pick } from "../../random.js";
import { swell } from "../../timing.js";

const COUNT = [2, 3];
const PLACE = [0.2, 1]; // of the safe radius about the pivot (geometry.js)
const RADIUS_PX = [16, 26]; // at 1080p
const ASPECT = [0.3, 0.6]; // the short axis, as a fraction of the long one
const COLOURS = [[1, 0.78, 0.3], [1, 0.9, 0.72]]; // gold, warm white
const RESOLVE_S = 1200;
const ALPHA = [0.25, 0.85]; // at the core, hazy to resolved
const HAZE_ALPHA = 0.6; // the wide haze, as a share of the core's alpha
const CORE_RADIUS = 0.35; // of the galaxy's radius

export default {
  name: "galaxies",
  family: "galaxies",
  layer: "behind",
  build(next, sky) {
    const galaxies = [];
    const count = Math.round(between(next, ...COUNT));
    const reach = safeRadius(sky);
    for (let i = 0; i < count; i++) {
      const distance = between(next, ...PLACE) * reach;
      const angle = next() * 2 * Math.PI;
      galaxies.push({
        x: distance * Math.cos(angle),
        y: distance * Math.sin(angle),
        radius: between(next, ...RADIUS_PX),
        aspect: between(next, ...ASPECT),
        tilt: next() * Math.PI,
        rgb: pick(next, COLOURS),
        resolve: { period: RESOLVE_S, phase: next() * 2 * Math.PI },
      });
    }
    return { galaxies };
  },
  draw(context, state, frame) {
    const [hazy, resolved] = ALPHA;
    for (const galaxy of state.galaxies) {
      const { x, y } = skyToCanvas(galaxy.x, galaxy.y, frame);
      const alpha = hazy + (resolved - hazy) * (1 - swell(frame.t, galaxy.resolve));
      const radius = galaxy.radius * frame.px;
      context.save();
      context.translate(x, y);
      context.rotate(galaxy.tilt + frame.rotation);
      context.scale(1, galaxy.aspect);
      fillSoftDisk(context, radius, galaxy.rgb, alpha * HAZE_ALPHA);
      fillSoftDisk(context, radius * CORE_RADIUS, galaxy.rgb, alpha);
      context.restore();
    }
  },
};

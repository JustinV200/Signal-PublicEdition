// Zoom-out (effects/): the sky shrinks about its pivot by one percent over the night,
// too slow to see happen, so dawn's sky is a little wider than dusk's.

import { nightProgress } from "../../timing.js";

const ZOOM_OUT = 0.01;

export default {
  name: "zoom-out",
  family: "zoom",
  build() {
    return {};
  },
  adjust(state, frame) {
    return { zoom: 1 - ZOOM_OUT * nightProgress(frame.t) };
  },
};

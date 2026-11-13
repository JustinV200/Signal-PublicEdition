// Fast rotation (effects/): the sky turns once every six hours instead of once a day,
// about a degree a minute, so the turn can be seen within minutes of watching.

const TURNS_PER_DAY = 4;

export default {
  name: "rotation",
  family: "rotation",
  build() {
    return {};
  },
  adjust(state, frame) {
    return { rotation: frame.rotation * TURNS_PER_DAY };
  },
};

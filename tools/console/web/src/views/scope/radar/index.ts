// Entry point of the radar: the scope's drawing parts, its label layout and
// the scale its distances are read against.
export { Blips } from "./Blips";
export { ringCaptions, sectorNames, signalCaption } from "./captions";
export { SIZE } from "./geometry";
export { Grid } from "./Grid";
export { boxOf, layoutLabels } from "./labels";
export { RadarText } from "./RadarText";
export { ageRange, percentRange, SECTORS, signalWords } from "./scale";
export type { Sector } from "./scale";
export { Sweep } from "./Sweep";
export type { Blip } from "./types";

# views/scope/radar

The scope's radar drawing: `Grid`, `Sweep`, `Blips` and `RadarText`, plus the label layout (`layoutLabels`, `boxOf`), captions, geometry (`SIZE`, `polar`) and the scale its distances and sectors are read against (`SECTORS`, `ageRange`, `percentRange`, `signalWords`).

Public API: `index.ts`. Depends on `state` (the `View` type), `ui` (`MarkPath`, `MarkShape`), `api` (`isStreamStale`) and `time` (`shortAge`).

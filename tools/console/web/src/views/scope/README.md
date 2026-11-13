# views/scope

The landing view: a radar scope and a text readout of the live state. `blips.ts` turns the store state into blips (Claude at the centre, the voice hub and the current board on the middle ring, pending requests on the outer ring; shape and label carry the meaning, pulsing while in flight, and Claude a ring pulsing slowly while only its agents run) and into the readout rows. `Scope` draws them in one SVG with range rings, a crosshair grid and a slow sweep that stops when the page is hidden or under `prefers-reduced-motion`. `ScopeView` lays the two out. No controls live here.

Public API: `index.ts`. Depends on `state`, `status` (phase and turn words), `time`, `ui` (page visibility).

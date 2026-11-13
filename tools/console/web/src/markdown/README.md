# markdown

`<Markdown text>` turns Claude's untrusted text into React elements with `react-markdown` + `remark-gfm`. Raw HTML is shown as literal text, only absolute `http(s)` URLs become links (`links.ts`), images render as a `[image] alt` link and never fetch, and nothing touches `innerHTML`.

Public API: `index.ts`. Depends on `react-markdown` and `remark-gfm` only.

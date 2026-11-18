# markdown

`<Markdown text>` turns Claude's untrusted text into React elements with `react-markdown` + `remark-gfm`. Raw HTML is shown as literal text, only absolute `http(s)` URLs become links (`links.ts`), images render as a `[image] alt` link and never fetch, and nothing touches `innerHTML`. `markdown.module.css` sets the look: 12px between blocks (under Chat's 16px between messages), headings at body size but h1 (+2px), h2 uppercase with 0.06em tracking, 4px from a heading to its section.

`<LinkedText text>` is for one line of plain text, such as where to get a missing program: it parses no Markdown and only turns the bare `http(s)` URLs in it into the same new-tab links (`linkParts` in `links.ts`; trailing sentence punctuation stays outside the link).

Public API: `index.ts`. Depends on `react-markdown` and `remark-gfm` only.

# Idle board: visual design

The look of the projector's default view. `plan.md` next to this covers data, refresh and wiring; this covers what goes where and how it reads from across the room. The mock is `mock.html` (open it from disk; `mock.html#debug` outlines every region and the glare keep-out). Its `layout.js` (the numbers), `parts.js` (shared pieces), `regions.js` (the data regions), `render.js` (assembly and top band), `mock.css` and `icons.js` are written to be lifted into `display/static/idle/` almost as they are; `data.js` is the payload shape.

## 1. The look

The Signal console's HUD, projected: mono uppercase labels with a thin rule running to the region's edge, one phosphor hue (the board's cyan) for all chrome, status as a number plus a word in an outlined chip (the console's `[1 review]` tag with the task grid's bold white number), course chips exactly as the TODO view draws them, `▸` for "the next one", a 2 px left rule for the priorities block, corner ticks in the margin. Body text is the board font (Segoe UI); the clock and temperature are Segoe UI Light, so the big digits are thin strokes. Nothing is filled, glows, bounces or uses an emoji: the page is black (no light), everything drawn is a thin stroke or text, so the owner's marker ink stays readable.

## 2. Grid (board pixels, 1112 x 720)

Content sits in (40, 44) to (1072, 680). The corner ticks sit in the margin ring, at the corners of (28, 34) to (1084, 690): if the top ticks are missing, the top is clipped; if a tick is off the board, the fit has drifted.

| Region | x, y, w, h | Holds | Slots |
|---|---|---|---|
| Dial | 40, 54, 96 x 96 | scope-style analogue dial, hour and minute hands only | |
| Clock | 148, 48, 240 x 108 | `HH:MM`, 24 h, no seconds | |
| Date | 390, 56, 326 x 104 | weekday (HUD label), `20 October` (36 px), usage line (20 px grey) | |
| Weather | 724, 54, 348 x 104, right-aligned | glyph 64 px, temperature, condition word, `H 64° L 48°`, `Rain 10%`, optional `as of HH:MM` | |
| Top rule | 40, 168, 1032 x 1.5 | cyan 60% | |
| Today | 40, 186, 560 x 282 | label row 28 + rows of 40 | 6 |
| Priorities | 40, 484, 560 x 140 | label row + rows of 34, behind a 2 px left rule | 3 |
| Divider | 620, 186, 1 x 450 | white 22% | |
| Agents | 640, 186, 432 x 176 | label row + lines of 34 | 4 lines |
| Upcoming | 640, 444, 432 x 196 | label row + rows of 32 | 5 |
| Foot rule | 40, 646, 1032 x 1 | white 22% | |
| News | 40, 652, 1032 x 28 | `NEWS` label, one headline line, source | 1 |

**Glare keep-out:** ellipse centred (815, 420), 180 x 120 (x 725 to 905, y 360 to 480). Only the UPCOMING label's rule crosses it. That is why AGENTS is capped at 4 lines (ends y 360) and UPCOMING starts at y 480. If a recalibration moves the hotspot, this gap can't follow it; keep the 4-line cap and the gap where they are rather than filling them.

Columns: left 40 to 600, right 640 to 1072. Rows never wrap; a row is one line, cut with an ellipsis.

## 3. Typography

Fonts already on the board page or the PC: Segoe UI (the board font), Segoe UI Light (weight 300, ships with Windows 11), Consolas (the console's fallback mono; IBM Plex Mono isn't served by the whiteboard daemon, vendor it later if the console look should match exactly). Tabular numbers everywhere. Nothing under 20 px.

| Use | Font | Size / weight |
|---|---|---|
| Clock | Segoe UI Light | 88 px / 300 |
| Temperature | Segoe UI Light | 60 px / 300 |
| Date | Segoe UI | 36 px / 400 |
| Weather condition word | Segoe UI | 24 px |
| Task text (today) | Segoe UI | 26 px |
| Headline | Segoe UI | 26 px |
| Agent name and %, priority text, event title, empty-state line | Segoe UI | 24 px |
| HUD labels (TODAY, AGENTS, weekday, NEWS) | Consolas bold, uppercase, letter-spacing 0.12em | 22 px |
| Due column, `YOU:` line, `+N more`, day column (Consolas bold) | Segoe UI / Consolas | 22 px |
| Course chip (Segoe UI 600), status chip (Consolas), counts, usage, source, `as of` | | 20 px |

Line heights: rows are fixed (40 / 34 / 32 px), text vertically centred.

## 4. Colour roles

Each colour has a non-colour cue, so the board also works for colourblind users; the colour is always the second signal.

| Colour | Used for | The other cue |
|---|---|---|
| White `#ffffff` | body text, clock, date, hands, temperature | |
| Cyan `#00e5ff` | HUD labels, rules, dial, day column, `1 review` chip | position and the label text |
| Yellow `#ffea00` | due text of today's items, `Today` in the day column, `▸` next marker, `2 building` chip, sun and bolt in glyphs | the words `today`, the glyph, the number 2 |
| Red `#ff5252` | the due word of overdue items (the TODO view's Overdue colour) | the word `overdue` |
| Pink `#ff99ff` (outline `#ff66ff`) | `3 YOU` chip and the `YOU:` prefix (the task grid's needs-you colour) | the number 3 and the word YOU |
| Lime `#7cff00` | `5 done` chip (task grid) | the number 5 |
| Grey `#90a4ae`, bright grey `#cfd8dc` | counts, usage, source, `as of`, `+N more`, empty states, later-day due text, high/low | smaller size and position |
| Course colours | chips, from `todo/view/payload.py`'s `tag_color` (sha256 of the tag): each tag gets its own bright colour (for example CHEM 120 yellow, HIST 205 lime) | the chip's text |

Status chip: number in bold white, word in the status colour, outline in the status colour: `1 review` cyan, `2 building` yellow, `3 YOU` pink, `4 queued` white, `5 done` lime (the task grid's key).

## 5. Regions

**Dial and clock.** Dial: ring r 44 (cyan 60%, 1.5 px), a faint inner range ring r 28 (the console scope's rings), 12 ticks (longer at the quarters), hour hand 22 px / 3.5 px stroke, minute hand 32 px / 2.5 px, centre pin. No seconds hand, no animation: the hands move only when the digits do, once a minute, so the camera's motion check sees nothing beyond the minute flip `plan.md` already handles. Clock `HH:MM`, 24 h. Date: weekday as a HUD label, `20 October` below, then the usage line `Claude 5h 42% · wk 18% · 5 agents` (grey, 20 px, cut with an ellipsis; omitted when usage is null).

**Weather.** Glyph, temperature `61°`, then a column: condition word, `H 64° L 48°`, `Rain 10%`. Stale (cache older than the refresh, per plan.md): add `as of 05:40` as a fourth line and dim the whole block to 60%. Unavailable: the dashed-circle glyph and `Weather unavailable` in grey. Glyphs are thin outlines in a 48-unit box (stroke 2.2, round caps), one colour accent each: sun and bolt yellow, rain cyan, cloud and moon and snow white, fog lines bright grey. The cloud is filled black so a sun or moon behind it is hidden where they overlap (black is no light). WMO `weather_code` from Open-Meteo, plus `is_day` (add `is_day` to the `current=` list in plan.md's call):

| Code | Word (day / night) | Glyph |
|---|---|---|
| 0 | Sunny / Clear | sun / moon |
| 1 | Mostly sunny / Mostly clear | partly-day / partly-night |
| 2 | Partly cloudy | partly-day / partly-night |
| 3 | Overcast | cloud |
| 45, 48 | Fog | fog |
| 51, 53, 55 | Drizzle | rain |
| 56, 57 | Icy drizzle | rain |
| 61, 63 / 65 | Rain / Heavy rain | rain |
| 66, 67 | Freezing rain | rain |
| 71, 73 / 75 | Snow / Heavy snow | snow |
| 77 | Snow grains | snow |
| 80, 81 / 82 | Showers / Heavy showers | rain |
| 85, 86 | Snow showers | snow |
| 95 | Thunderstorm | storm |
| 96, 99 | Hail storm | storm |
| anything else | Cloudy | cloud |

Words stay under 14 characters so they fit the 176 px words column at 24 px.

**Today.** Label row `TODAY · 1 overdue · 2 today` (counts exclude done items). Rows: chip column 120 px, text, due column 84 px right-aligned. Order: overdue (oldest first), today (by time, untimed last), then the next days' dated items until the slots are used. Due text: `overdue` (red) for overdue; the time, or `today` when untimed, in yellow for today; the weekday (`Wed`) or `4 Nov` beyond six days, in bright grey. An item ticked today stays, struck through in its tag colour and dimmed to 38% (the TODO view's rule and animation, `todo-strike` then `todo-dim`), and is dropped first when over budget. Overflow: 6 slots; past that, 5 rows and `+N more`. Text rule, no model: the item text without its due note, cut at the first `:`, `;` or ` (` when longer than the row, then an ellipsis. Empty: `Nothing due today`. Updates with plan.md's 15 s mtime check and at midnight.

**Priorities.** Label `PRIORITIES`, up to 3 rows behind a 2 px cyan left rule: chip column 120 px and the line's text cut as above. Source: the week plan's `## Priorities` (plan.md). More than 3: only the first 3, no more-line (the list is curated). Empty: `No priorities this week` (the region keeps its place so the layout never shifts; plan.md said hide, this keeps every region where the owner expects it).

**Agents.** Label row `AGENTS · 3 active · 6 queued · 3 done`. One line per active task: status chip (124 px), name (cut), `70%`, and a 2 px progress line under name and % (track white 18%, done part in the status colour). Order: tasks that need the owner first, then by % done, highest first (the task grid's order). The first needs-you task gets a second line `YOU: <what the owner must do>` (22 px, `YOU:` bold pink); later ones show only the chip. Budget: 4 lines; past that, 3 lines and `+N more` (N counts tasks whose row isn't shown). Queued and done appear only as counts in the label row. Empty: `No agent tasks`. Updates on `tasks.json` and `usage.json` mtime.

**Upcoming.** Label `UPCOMING`. Rows: day column 64 px in Consolas bold (`Today` yellow, else the weekday `Wed` in cyan), chip column 120 px, title (cut). The first row's title starts with a yellow `▸`. Source and order per plan.md: the next 7 days' dated plan items after today plus `schedule.md` rows, by date then time; the time goes into the title text (`Midterm exam 14:00, Room 101`), deadlines at end of day show no time. 5 slots; past that, 4 rows and `+N more`. Empty: `No dates this week`.

**News.** A footer line: `NEWS` label, a ticker window, the source name in grey at the right (the `[idle] news_source` label, "AllSides" by default). The ticker scrolls the feed's top 6 fresh headlines (26 px) right to left like a TV news crawl, separated by a cyan `•`, at `[idle] ticker_px_s` (75 design px/s), looping seamlessly; new headlines join where the list starts over, so nothing jumps. The label and source stay put. Empty or stale past 6 h: `No headline` in grey. Updates every 30 min. The camera's motion check leaves the footer band out (`display/server/board/idle_ticker.py`).

## 6. Motion

None, except: the news ticker scrolls (see News; the camera ignores its band); the clock digits and dial hands change on the minute; a region whose data changed cross-fades its rows (opacity 0 to 1, 400 ms, `--ease-out`), nothing moves; a task ticked today gets the TODO view's strike animation once. Under `prefers-reduced-motion: reduce`, no fades either. Pushes are already limited to once a minute by plan.md.

## 7. Building it

- Lift the four JS files into `display/static/idle/` as ES modules (`render.js` becomes `idle.js`, the entry point), `mock.css` into `idle.css` (drop the page chrome), `icons.js` into `glyphs.js` built with `createElementNS` instead of strings. Keep `LAYOUT`, `SLOTS`, `GLARE` and `TAG_LABELS` as the constants; the layout can live in the page, since unlike the TODO view nothing in the daemon needs row positions (no cross-out checks here).
- The payload is `data.js`'s shape plus `as_of`/`stale` per region from plan.md. Every string goes in with `textContent`, as the mock does.
- Chip labels: `TAG_LABELS` gives each tag a display name under 10 characters (`Side Proj`, `CHEM 120`); unknown tags are title-cased with dashes as spaces. Make it `[idle] tag_labels` in `whiteboard.toml` so a new course needs no code.
- Check it on the real board with `board_look(clean=false)` after the first draw: the glare keep-out and the 40 px margin are from today's fit.

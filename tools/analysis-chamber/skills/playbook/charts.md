# Charts

Never use colour alone for meaning. A chart a reader can't read is a broken
chart. These rules aren't optional.

## Colour

- Categorical series: the Okabe-Ito palette, in this order:
  `#000000` black, `#E69F00` orange, `#56B4E9` sky blue, `#009E73` bluish green,
  `#F0E442` yellow, `#0072B2` blue, `#D55E00` vermillion, `#CC79A7` reddish purple.
  Skip yellow on white backgrounds for thin lines.
- Sequential values (heatmaps, choropleths): `viridis` or `cividis`.
- Diverging values: purple-orange (`PuOr`) or blue-red (`RdBu`), centred on
  the meaningful zero.
- **Never red vs green**, including "good = green, bad = red". Never rainbow or
  `jet`.
- Max ~6 categories in one chart. Past that, group the tail into "Other", or
  split into small multiples.

## Colour is never the only signal

Every series must also be told apart by at least one of:
- a distinct marker (`o`, `s`, `^`, `D`, `v`, `x`) on lines and scatters
- a distinct line style (`-`, `--`, `-.`, `:`)
- a direct label at the end of the line or on the bar (preferred over a legend)
- a hatch pattern on bars or areas

If you removed all colour from the chart, it should still read correctly.

## Numbers and text

- Put the value on the key bars (`ax.bar_label`), formatted with units and
  sensible rounding ("42%", "$118k").
- Title states the finding, not the topic: "Median rent rose 18%
  between 2020 and 2025", not "Rent by year".
- A subtitle or caption gives the source and date range.
- Axis labels always include units: "Rent (USD per month)", "Listings per week".
- Font size at least 11 pt; text must read at the size it's shown.
- Status and confidence on charts are words (High / Medium / Low), never only a
  colour code.

## Honesty

- Bar charts start at zero. Line charts may not, but say so if the cut changes
  the impression.
- Show uncertainty: error bars or shaded bands with a note saying what they are
  (95% CI, 80% PI, +/- 1 SD).
- Same scale across small multiples unless you say otherwise.
- No 3D, no dual y-axes (use two panels), no pie charts with more than 3 slices.
- Don't truncate time ranges to hide inconvenient periods.
- Show counts for percentages from small bases.

## Code

matplotlib for static PNGs, plotly for interactive charts in HTML reports.

```python
import matplotlib.pyplot as plt
from cycler import cycler

OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73",
             "#0072B2", "#D55E00", "#CC79A7"]
plt.rcParams["axes.prop_cycle"] = (
    cycler(color=OKABE_ITO)
    + cycler(marker=["o", "s", "^", "D", "v", "P", "X"])
    + cycler(linestyle=["-", "--", "-.", ":", "-", "--", "-."])
)
plt.rcParams.update({"font.size": 11, "figure.dpi": 150})
```

For plotly, pass `color_discrete_sequence=OKABE_ITO` and also set `symbol=` or
`line_dash=` to the same column as `color=`.

## Saving

- Save every chart as PNG to `figures/` with a descriptive name
  (`figures/03_rent_by_year.png`), `bbox_inches="tight"`.
- The script that made it is in `code/` with a matching number.
- Each figure in the report gets alt text that states the finding in words.

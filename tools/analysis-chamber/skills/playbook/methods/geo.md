# Geo data

Locations, addresses, regions: store counts by city, rents by neighbourhood,
anything with coordinates or place names.

## Prepare

- Use `geopandas` and `shapely` (not in the kit; install per
  `../gpu-and-installs.md`). duckdb's `spatial` extension handles big point
  sets fast.
- Get coordinates into one CRS. Store in WGS84 (EPSG:4326); project to a local
  metric CRS in metres (e.g. a city's local projected CRS such as a UTM zone;
  avoid feet-based CRSs such as State Plane zones in US survey feet; check the unit) before measuring distance
  or area. Degrees aren't metres.
- Geocoding: prefer a data file with codes already in it (FIPS, ZIP, ISO). If you
  must geocode, use a free service with its rate limit (Nominatim: 1 request per
  second, with a user agent), cache results in `data/clean/`, and report the
  match rate.
- Boundaries: download official shapefiles (Census TIGER, a city open-data portal) as data
  files. Note the vintage year; ZIPs and tracts change.

## Pick the question type

Most geo questions are a normalised table or map per region. Models are rare.

| If the question is... | Then start with | Step up to |
|---|---|---|
| "Where is there more X?" | counts per region, *normalised* (per capita, per km2) | kernel density, hex bins (`h3`) |
| "Is X clustered?" | nearest-neighbour distances vs random | Moran's I / local LISA (`esda`, `libpysal`) |
| "What's near what?" | spatial join (`gpd.sjoin`), buffers | travel time from a routing API |
| "Does location predict Y?" | region fixed effects in a regression | spatial lag models; lat/lon + region features in lightgbm |

## Traps

- Raw counts per region mostly map population. Always normalise, and say by what.
- Small regions with few cases give extreme rates. Pool, smooth (empirical
  Bayes), or suppress regions under a minimum count, and say which.
- The modifiable areal unit problem: results change with the boundary scale.
  If the finding matters, check it at a second scale.
- Nearby places are correlated, so ordinary CIs are too narrow. For CIs, use
  cluster-robust SEs by region (`cov_type="cluster"`) or a spatial model. For
  cross-validation, use spatial blocks (group k-fold by region).

## Maps

- Choropleths use a sequential colour map (viridis or cividis) with a labelled
  legend that shows the numbers and units. Never red/green.
- Annotate the top few regions with their values directly on the map, so the
  map reads without the colour scale.
- If the question is about ranking, a sorted bar chart beats a map. Use a map
  only when the spatial pattern is the point.
- Save static maps as PNG to `figures/`. Interactive plotly maps only in an HTML
  report.

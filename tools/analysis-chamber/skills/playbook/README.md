# playbook

The methods playbook skill for the analysis chamber. The lead agent of every run
reads `SKILL.md` before it analyses anything, then opens the reference files it
needs. The critic agent checks the run against `critic.md`.

The user can edit any of these files. Changes take effect on the next run, since the
daemon loads the playbook from the path in `config.toml`.

## Files

| File | Covers |
|---|---|
| `SKILL.md` | entry point: how to use the playbook, run folder, core workflow |
| `methods/tabular.md` | regression, classification, clustering on tables |
| `methods/time-series.md` | trends, seasonality, forecasting, change points |
| `methods/text.md` | embeddings, topics, classification, LLM extracts |
| `methods/graph.md` | networks, centrality, communities |
| `methods/geo.md` | spatial joins, maps, spatial stats |
| `methods/web-research.md` | source quality, triangulation, polite fetching |
| `validation.md` | leakage, splits, baselines, stats, confidence words |
| `charts.md` | colourblind-safe chart rules |
| `gpu-and-installs.md` | GPU lock and run-venv installs |
| `reporting.md` | report and writeup contents and format choice |
| `critic.md` | the critic's checklist and `critique.md` format |

Keep each file under about 150 lines and in "if X then Y, else Z" style.

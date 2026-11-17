# Graph data

Entities and links: who emails whom, which companies hire from which schools,
citation or link networks, co-occurrence of topics.

## Build the graph

- Use `networkx` (it's in the kit). Over ~1M edges, compute with duckdb or scipy sparse
  matrices and keep networkx for small subgraphs.
- Decide up front and write down: what a node is, what an edge is, directed or
  not, and what the weight means (count, recency, amount).
- Merge entity aliases first (same person, two email addresses). Bad entity
  resolution breaks every metric after it.
- Save the edge list to `data/clean/edges.parquet`.

## Pick the question type

Degree counts and a top-N table answer most questions. Go further only if needed.

| If the question is... | Then start with | Step up to |
|---|---|---|
| "Who or what is most central?" | degree (weighted) | PageRank, betweenness on a sample |
| "What groups exist?" | connected components | Louvain / Leiden communities (`networkx.community`) |
| "How do A and B connect?" | shortest paths | k shortest paths, flow |
| "What links will form?" | common neighbours, Adamic-Adar | node2vec / GNN embeddings (PyTorch) only for large graphs |
| "How did the network change?" | metrics per time slice | community tracking across slices |

## Rules

- Centrality depends on the measure. If degree and PageRank disagree on the top
  10, report both and say what each means.
- Communities from Louvain change between runs. Run it with 5+ different
  seeds, keep only groups that are stable across them, then fix one seed for
  the partition you report.
- Compare against a null model before calling a structure surprising: a
  degree-preserving random graph (`nx.double_edge_swap`, or
  `nx.directed_edge_swap` for directed graphs) gives the
  baseline for clustering and community strength.
- Sampled or partial graphs (one inbox, one site crawl) are biased towards the
  sampled node. Say so.

## Personal-data graphs

- Contacts are people. Refer to them in the report the way the source does, but
  keep raw addresses and numbers out of chart labels unless they're needed.

## Charts

- Force-directed hairballs over ~100 nodes say nothing. Show the top-N subgraph,
  a community-level summary graph, or a ranked bar chart of centrality instead.
- Label nodes directly. Distinguish communities by marker shape plus colour,
  per `../charts.md`.

# GPU and installs

## The kit and the run venv

Each run has its own venv at `<run>\.venv`, layered on a shared kit venv. The
daemon puts `<run>\.venv\Scripts` first on PATH and sets `VIRTUAL_ENV` to it,
so plain `python` always means the run venv. Never call the
kit's python directly.

The kit already has: pandas, polars, pyarrow, duckdb, scipy, statsmodels,
scikit-learn, xgboost, lightgbm, PyTorch with CUDA, sentence-transformers,
transformers, networkx, plotly, matplotlib, openpyxl, requests, and jupyter
(with nbconvert and ipykernel). Prefer kit packages. If the kit can do it,
don't install an alternative.

## The GPU lock

The GPU (check its memory with `nvidia-smi`) is shared by up to 3 runs. Only one GPU-heavy step may run
at a time. Wrap every GPU-heavy command:

```
analysis-chamber gpu -- python code/05_train.py
```

`python` here is the run venv's python (it's first on PATH). The wrapper waits
for the lock, runs the command, and releases the lock when it exits.

- **Use it for:** PyTorch training or inference, sentence-transformers encoding
  of more than a few hundred texts, xgboost/lightgbm with GPU device set, and
  anything else that puts real load on CUDA.
- **Don't use it for:** CPU-only work (pandas, statsmodels, CPU lightgbm). Holding
  the lock for CPU work blocks other runs.
- Keep locked steps short and self-contained: load, compute, save results to
  `models/` or `data/clean/`, exit. Do the analysis of the outputs afterwards,
  outside the lock.
- The lock is not re-entrant. Never nest `analysis-chamber gpu`: don't wrap a
  script that itself calls it, or the inner call waits forever.
- Never start GPU work in a background process or a long-lived Python session
  that outlives the wrapped command.
- If you hit CUDA out of memory: lower the batch size, use fp16
  (`torch.autocast`), or run on CPU if it's small. Free memory with
  `del model; torch.cuda.empty_cache()` between models in one script.
- Check the GPU is used: `torch.cuda.is_available()` should be True inside the
  wrapped command. If it's False, say so and fall back to CPU.

## Installs

Install with the chamber's own command, run from the run folder root, never
with `pip` or `uv pip` directly:

```
analysis-chamber install <pkg> [<pkg> ...]
```

It resolves against the kit and installs only what the kit lacks, into the run
venv. Torch-dependent packages get their torch from the CUDA (cu132) index, so
the GPU build stays intact. It refuses to replace a kit package with a different
version.

1. **Check first.** Run `python -c "import <module>"`. If it imports, you
   already have it; don't install anything.
2. **Install** with `analysis-chamber install`.
3. **If it refuses** because a kit package would be shadowed, prefer another
   package or an older version of yours that fits the kit. Only when nothing
   else works, pass `--allow-shadow`, listing each conflicting dependency
   itself (check `analysis-chamber install --help` for the exact form), and say
   in `results.md` which kit package was shadowed and why. Shadowing a compiled
   core (numpy, scipy, pyarrow) can break other kit packages.
4. **torch is never shadowed**, even with `--allow-shadow`. If a package needs
   a different torch, pick another package.

- Installs are logged automatically into `manifest.installs[]`. The report's
  methods section lists them; copy them from the manifest.
- Prefer well-known packages with many users. Check the spelling of names
  before installing.
- If a package won't build on Windows, look for one that ships wheels before
  fighting the build.

Common extras that are fine to install when needed: `geopandas`, `shapely`,
`esda`, `libpysal`, `h3`, `umap-learn`, `hdbscan`, `ruptures`, `shap`,
`yfinance`, `fredapi`.

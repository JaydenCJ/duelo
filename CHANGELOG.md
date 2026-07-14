# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Bradley-Terry maximum-likelihood fitting via Hunter's MM algorithm, with
  ties counted as half a win per side and centered log-strengths reported
  on a configurable Elo-like display scale (`--base`, `--scale`).
- Analytic (Wald) confidence intervals from the observed Fisher
  information, with the singular direction handled by a reduced-matrix
  inverse and the delta method — pure-Python Gauss-Jordan, no numeric
  dependencies.
- Deterministic nonparametric bootstrap confidence intervals (percentile,
  seeded, default 200 rounds) for both Bradley-Terry and Elo, with a
  documented `1e-6` smoothing prior that keeps degenerate resamples
  fittable.
- Sequential Elo with configurable K-factor, initial rating, and curve
  scale; analytic CIs are refused for Elo with an explanatory error
  instead of a silently different answer.
- Fit-health checks before ranking: shutout (degenerate) items and
  disconnected comparison graphs raise typed errors that name the items
  and suggest `--prior`; `--prior t` adds pseudo-ties to every pair to
  repair both.
- Battle-log ingestion from JSON Lines and CSV with alias auto-detection
  (`a`/`model_a`/`left`/..., `winner`/`outcome`/`result`), arena-style
  winner values (`tie (bothbad)` etc.), custom column names
  (`--col-a`/`--col-b`/`--col-winner`), stdin via `-`, and loud
  line-numbered parse errors — malformed rows are never silently skipped.
- `duelo` CLI: `rank`, `elo`, `matrix` (exact W-L-T head-to-head cells),
  and `stats` (volume, pair coverage, connected components, degenerate
  items), each rendering to `table`, `markdown`, `json`, or `csv`.
- Library API re-exported from the package root (`load_battles`,
  `rank_bradley_terry`, `rank_elo`, `fit_bradley_terry`, `run_elo`,
  bootstrap helpers, typed errors).
- Runnable examples (deterministic 400-battle sample log with known true
  strengths, generator script, library walkthrough) and design docs
  (`docs/methodology.md`, `docs/formats.md`).
- 92 deterministic offline tests plus `scripts/smoke.sh`, an end-to-end
  CLI check that prints `SMOKE OK`.

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/duelo/releases/tag/v0.1.0

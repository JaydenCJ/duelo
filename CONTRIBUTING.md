# Contributing to duelo

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/duelo
cd duelo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 92 unit + CLI tests, fully offline
bash scripts/smoke.sh  # end-to-end: rank, elo, matrix, stats, error paths
```

Both must pass before a pull request is reviewed; `smoke.sh` must print
`SMOKE OK`. Everything runs offline in a few seconds and needs no services.

## Ground rules

- **No runtime dependencies.** The package is standard-library only; that
  is the point of the project. Test-only dependencies belong in the `dev`
  extra, and adding one needs justification in the PR.
- **Math changes need receipts.** Anything touching the fit, the Fisher
  information, or the bootstrap must update `docs/methodology.md` and add
  a test against a closed-form or otherwise independently known value.
- **Determinism is a feature.** No wall-clock, no network, no unseeded
  randomness anywhere — bootstrap draws must stay reproducible from
  `--seed`.
- **Every public API needs an English docstring and a test.** Keep logic
  in pure, unit-testable modules; the CLI stays a thin layer.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` are line-for-line parallel; update all three when you
  change one (English is the authoritative version).

## Reporting bugs

Please include `duelo --version`, the exact command line, and a minimal
battle log that reproduces the issue (a dozen JSONL lines is usually
enough). For ranking disputes, `duelo stats` and `duelo matrix` output of
the same log makes diagnosis much faster.

## Security

Do not open public issues for security problems; use GitHub private
vulnerability reporting on the repository instead.

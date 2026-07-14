# duelo examples

Runnable from a plain checkout — no install needed, the package has zero
runtime dependencies:

```bash
cd duelo
PYTHONPATH=src python3 -m duelo rank examples/battles.jsonl
PYTHONPATH=src python3 examples/rank_from_python.py
```

## Files

| File | What it shows |
|---|---|
| `battles.jsonl` | 400 simulated battles between five fictional models with **known** true strengths (`nova-large` > `crest-2` > `puffin-xl` > `nova-mini` > `harbor-1`), 8% tie rate. Good for checking that duelo recovers the truth. |
| `generate_battles.py` | The deterministic generator for `battles.jsonl` (fixed seed, pure stdlib). Edit the true strengths and regenerate to build your own test cases. |
| `rank_from_python.py` | Library usage: load a log, fit Bradley-Terry with bootstrap CIs, print a leaderboard, and query a head-to-head win probability. |

## Things to try

```bash
# Bootstrap instead of analytic intervals — same seed, same numbers, every run
PYTHONPATH=src python3 -m duelo rank examples/battles.jsonl --ci bootstrap --seed 42

# How lopsided are the head-to-heads?
PYTHONPATH=src python3 -m duelo matrix examples/battles.jsonl

# Is this log even fittable? (connectivity, shutouts, coverage)
PYTHONPATH=src python3 -m duelo stats examples/battles.jsonl

# Machine-readable output for your own dashboards
PYTHONPATH=src python3 -m duelo rank examples/battles.jsonl --format json
```

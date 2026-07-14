# Input and output formats

## Battle logs (input)

One battle = two item names + an outcome. duelo reads JSON Lines and CSV;
`--input-format` forces one, otherwise the extension and then the content
decide (`.csv` → CSV; `.jsonl`/`.ndjson`/`.json` → JSONL; unknown
extensions are sniffed by the first non-blank line).

### JSON Lines

One JSON object per line. Blank lines and lines starting with `#` are
skipped. Keys are auto-detected from these aliases, in order:

| Field | Aliases tried |
|---|---|
| first item | `a`, `model_a`, `left`, `player_a` |
| second item | `b`, `model_b`, `right`, `player_b` |
| winner | `winner`, `outcome`, `result` |

```jsonl
{"a": "nova-large", "b": "crest-2", "winner": "a"}
{"model_a": "crest-2", "model_b": "puffin-xl", "winner": "tie"}
```

### CSV

A header row is required; extra columns (timestamps, judges, prompts) are
ignored. The same aliases apply, or name the columns explicitly:

```bash
duelo rank prefs.csv --col-a champ --col-b challenger --col-winner verdict
```

### Winner values

Accepted, case-insensitively for labels:

| Value | Meaning |
|---|---|
| `a`, `model_a`, `left`, `player_a`, `1` | first item won |
| `b`, `model_b`, `right`, `player_b`, `2` | second item won |
| `tie`, anything starting with `tie` (e.g. `tie (bothbad)`), `draw`, `both`, `both_bad` | tie |
| the exact (case-sensitive) name of either item | that item won |
| your own `--col-a` / `--col-b` names | that side won |

Anything else is a `ParseError` naming the file and line — rows are never
silently dropped, because silent drops bias the ranking.

## Leaderboard JSON (output)

`--format json` emits a stable, sorted-keys document (the values below are
real output for `examples/battles.jsonl`, truncated to the first item):

```json
{
  "ci": {"level": 0.95, "method": "analytic"},
  "items": [
    {"ci_high": 1228.0968, "ci_low": 1123.6558, "games": 164, "losses": 32,
     "name": "nova-large", "rank": 1, "rating": 1175.8763, "ties": 13,
     "win_rate": 0.7652, "wins": 119}
  ],
  "meta": {"base": 1000.0, "converged": true, "iterations": 69, "prior": 0.0, "scale": 400.0},
  "method": "bradley-terry",
  "n_battles": 400,
  "n_ties": 35
}
```

* `rating`, `ci_low`, `ci_high` are on the display scale (`base`/`scale`),
  rounded to 4 decimals.
* `ci_low`/`ci_high` are `null` when `--ci none`.
* `win_rate` counts ties as half a win.
* Bootstrap runs add `"rounds"` and `"seed"` to `meta`, so a leaderboard
  is reproducible from its own output.

`matrix --format json` lists each unordered pair once with integer
`wins`/`losses`/`ties` from the first item's perspective; `stats --format
json` reports totals, pair coverage, connected components, and degenerate
items (`stats --format csv` carries the per-item table only).

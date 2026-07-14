#!/usr/bin/env bash
# Smoke test for duelo: build a small battle log, run every subcommand end to
# end, and assert on real output — ranking order, CI bounds, exit codes,
# error paths, and the version string.
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies: running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/duelo-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. Build a deterministic log with a known pecking order: ace > mid > rook.
LOG="$WORKDIR/battles.jsonl"
"$PYTHON" - "$LOG" <<'PYEOF'
import json, sys
rows = []
rows += [{"a": "ace", "b": "mid", "winner": "a"}] * 14
rows += [{"a": "mid", "b": "ace", "winner": "a"}] * 5
rows += [{"a": "ace", "b": "mid", "winner": "tie"}] * 2
rows += [{"a": "mid", "b": "rook", "winner": "a"}] * 12
rows += [{"a": "rook", "b": "mid", "winner": "a"}] * 6
rows += [{"a": "rook", "b": "ace", "winner": "b"}] * 10
rows += [{"a": "ace", "b": "rook", "winner": "b"}] * 3
rows += [{"a": "rook", "b": "ace", "winner": "tie"}] * 1
with open(sys.argv[1], "w") as fh:
    for row in rows:
        fh.write(json.dumps(row) + "\n")
print(f"wrote {len(rows)} battles")
PYEOF

# 2. stats: healthy log, one component, no degenerate items.
stats_out="$("$PYTHON" -m duelo stats "$LOG")"
echo "$stats_out" | sed 's/^/[stats] /'
echo "$stats_out" | grep -q "battles:     53" || fail "stats battle count wrong"
echo "$stats_out" | grep -q "components:  1" || fail "stats should report one component"
echo "$stats_out" | grep -q "degenerate:  none" || fail "stats should report no degenerate items"

# 3. rank: Bradley-Terry with analytic CIs, correct order, bounds present.
rank_out="$("$PYTHON" -m duelo rank "$LOG")"
echo "$rank_out" | sed 's/^/[rank] /'
echo "$rank_out" | grep -q "bradley-terry leaderboard" || fail "rank missing title"
echo "$rank_out" | grep -Eq '^ *1 +ace ' || fail "ace should rank first"
echo "$rank_out" | grep -Eq '^ *3 +rook ' || fail "rook should rank last"
echo "$rank_out" | grep -q '\.\.' || fail "rank output missing CI bounds"

# 4. rank --ci bootstrap is deterministic under a fixed seed.
boot1="$("$PYTHON" -m duelo rank "$LOG" --ci bootstrap --rounds 100 --seed 7)"
boot2="$("$PYTHON" -m duelo rank "$LOG" --ci bootstrap --rounds 100 --seed 7)"
[ "$boot1" = "$boot2" ] || fail "bootstrap CIs not reproducible with the same seed"

# 5. rank --format json is machine-readable and consistent with the table.
json_out="$("$PYTHON" -m duelo rank "$LOG" --format json)"
echo "$json_out" | "$PYTHON" -c '
import json, sys
payload = json.load(sys.stdin)
names = [item["name"] for item in payload["items"]]
assert names == ["ace", "mid", "rook"], names
top = payload["items"][0]
assert top["ci_low"] < top["rating"] < top["ci_high"]
' || fail "rank JSON payload malformed"

# 6. elo: same top item on this lopsided log.
elo_out="$("$PYTHON" -m duelo elo "$LOG" --ci none)"
echo "$elo_out" | sed 's/^/[elo] /'
echo "$elo_out" | grep -Eq '^ *1 +ace ' || fail "elo should also rank ace first"

# 7. matrix: exact W-L-T reconstruction for ace vs mid (14+0 W, 5 L, 2 T).
matrix_out="$("$PYTHON" -m duelo matrix "$LOG")"
echo "$matrix_out" | sed 's/^/[matrix] /'
echo "$matrix_out" | grep -q "14-5-2" || fail "matrix W-L-T cell wrong"

# 8. Degenerate log: exit 1 with a --prior hint; --prior repairs it.
DEGEN="$WORKDIR/shutout.jsonl"
printf '%s\n' '{"a": "top", "b": "bottom", "winner": "a"}' \
               '{"a": "top", "b": "bottom", "winner": "a"}' > "$DEGEN"
set +e
degen_err="$("$PYTHON" -m duelo rank "$DEGEN" 2>&1)"
degen_rc=$?
set -e
[ "$degen_rc" -eq 1 ] || fail "degenerate log should exit 1, got $degen_rc"
echo "$degen_err" | grep -q -- "--prior" || fail "degenerate error missing --prior hint"
"$PYTHON" -m duelo rank "$DEGEN" --prior 0.5 >/dev/null \
  || fail "--prior 0.5 should make the degenerate log rankable"

# 9. --version agrees with the package version.
version_out="$("$PYTHON" -m duelo --version)"
pkg_version="$("$PYTHON" -c 'import duelo; print(duelo.__version__)')"
[ "$version_out" = "duelo $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"

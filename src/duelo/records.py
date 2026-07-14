"""Reading pairwise preference logs.

A *battle* is one pairwise comparison: two item names and an outcome
(``"a"``, ``"b"``, or ``"tie"``). Battles are loaded from JSON Lines or CSV
files; the column/key names are auto-detected from a small set of common
aliases (``a``/``b``, ``model_a``/``model_b``, ``left``/``right``) or given
explicitly. Winner values are normalized generously: ``a``, ``b``,
``model_a``, ``model_b``, ``tie``, ``draw``, anything starting with ``tie``
(so arena-style ``"tie (bothbad)"`` works), or the literal name of one of
the two contestants.

Parsing is strict where it matters: an unknown winner value or a missing
field is a :class:`~duelo.errors.ParseError` with the file and line number,
never a silently skipped row.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .errors import ParseError

# Key aliases tried, in order, when no explicit column names are given.
A_KEYS: Tuple[str, ...] = ("a", "model_a", "left", "player_a")
B_KEYS: Tuple[str, ...] = ("b", "model_b", "right", "player_b")
WINNER_KEYS: Tuple[str, ...] = ("winner", "outcome", "result")

OUTCOME_A = "a"
OUTCOME_B = "b"
OUTCOME_TIE = "tie"


@dataclass(frozen=True)
class Battle:
    """One pairwise comparison. ``outcome`` is ``"a"``, ``"b"`` or ``"tie"``."""

    a: str
    b: str
    outcome: str

    def __post_init__(self) -> None:
        if self.outcome not in (OUTCOME_A, OUTCOME_B, OUTCOME_TIE):
            raise ValueError(f"invalid outcome {self.outcome!r}")
        if not self.a or not self.b:
            raise ValueError("battle items must be non-empty strings")
        if self.a == self.b:
            raise ValueError(f"battle pits {self.a!r} against itself")

    @property
    def winner(self) -> Optional[str]:
        """The winning item name, or ``None`` for a tie."""
        if self.outcome == OUTCOME_A:
            return self.a
        if self.outcome == OUTCOME_B:
            return self.b
        return None


def normalize_winner(
    value: str,
    a: str,
    b: str,
    a_label: Optional[str] = None,
    b_label: Optional[str] = None,
) -> str:
    """Map a raw winner value to ``"a"``/``"b"``/``"tie"``.

    Accepts side labels (case-insensitive; the built-in aliases plus the
    log's own column names when given), tie spellings, or the exact
    (case-sensitive) name of either contestant. Contestant names win over
    side labels only when unambiguous — e.g. items literally named ``"a"``
    still resolve correctly because both interpretations agree.
    """
    raw = value.strip()
    # Exact item names first: they are case-sensitive user data.
    if raw == a and raw != b:
        return OUTCOME_A
    if raw == b and raw != a:
        return OUTCOME_B
    lowered = raw.lower()
    a_aliases = {"a", "model_a", "left", "player_a", "1"}
    b_aliases = {"b", "model_b", "right", "player_b", "2"}
    if a_label:
        a_aliases.add(a_label.lower())
    if b_label:
        b_aliases.add(b_label.lower())
    if lowered in a_aliases:
        return OUTCOME_A
    if lowered in b_aliases:
        return OUTCOME_B
    if lowered in ("draw", "both", "both_bad", "bothbad") or lowered.startswith("tie"):
        return OUTCOME_TIE
    raise ValueError(
        f"unrecognized winner value {value!r} (expected 'a', 'b', 'tie', "
        f"or one of the item names {a!r} / {b!r})"
    )


def _pick_key(available: Sequence[str], aliases: Sequence[str], what: str) -> str:
    for alias in aliases:
        if alias in available:
            return alias
    raise ValueError(
        f"could not find a {what} column; looked for {', '.join(aliases)} "
        f"among {sorted(available)}"
    )


def _battle_from_mapping(
    row: dict,
    a_key: Optional[str],
    b_key: Optional[str],
    winner_key: Optional[str],
) -> Battle:
    keys = list(row.keys())
    ka = a_key or _pick_key(keys, A_KEYS, "first-item")
    kb = b_key or _pick_key(keys, B_KEYS, "second-item")
    kw = winner_key or _pick_key(keys, WINNER_KEYS, "winner")
    for key in (ka, kb, kw):
        if key not in row or row[key] is None or str(row[key]).strip() == "":
            raise ValueError(f"missing value for {key!r}")
    a = str(row[ka]).strip()
    b = str(row[kb]).strip()
    outcome = normalize_winner(str(row[kw]), a, b, a_label=ka, b_label=kb)
    return Battle(a=a, b=b, outcome=outcome)


def parse_jsonl(
    lines: Iterable[str],
    source: str = "<jsonl>",
    a_key: Optional[str] = None,
    b_key: Optional[str] = None,
    winner_key: Optional[str] = None,
) -> List[Battle]:
    """Parse JSON Lines. Blank lines and ``#`` comment lines are skipped."""
    battles: List[Battle] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ParseError(f"invalid JSON: {exc.msg}", source, lineno) from exc
        if not isinstance(row, dict):
            raise ParseError("expected a JSON object per line", source, lineno)
        try:
            battles.append(_battle_from_mapping(row, a_key, b_key, winner_key))
        except ValueError as exc:
            raise ParseError(str(exc), source, lineno) from exc
    return battles


def parse_csv(
    text: str,
    source: str = "<csv>",
    a_key: Optional[str] = None,
    b_key: Optional[str] = None,
    winner_key: Optional[str] = None,
) -> List[Battle]:
    """Parse CSV with a header row. Extra columns are ignored."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ParseError("empty CSV file (no header row)", source, 1)
    battles: List[Battle] = []
    for row in reader:
        lineno = reader.line_num
        clean = {k: v for k, v in row.items() if k is not None}
        if all(v is None or str(v).strip() == "" for v in clean.values()):
            continue  # blank trailing line
        try:
            battles.append(_battle_from_mapping(clean, a_key, b_key, winner_key))
        except ValueError as exc:
            raise ParseError(str(exc), source, lineno) from exc
    return battles


def sniff_format(path: str, text: str) -> str:
    """Guess ``"csv"`` or ``"jsonl"`` from the extension, then the content."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return "csv"
    if ext in (".jsonl", ".ndjson", ".json"):
        return "jsonl"
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return "jsonl" if stripped.startswith("{") else "csv"
    return "jsonl"


def load_battles(
    path: str,
    fmt: str = "auto",
    a_key: Optional[str] = None,
    b_key: Optional[str] = None,
    winner_key: Optional[str] = None,
) -> List[Battle]:
    """Load battles from ``path`` (``"-"`` reads stdin).

    ``fmt`` is ``"auto"`` (default), ``"jsonl"`` or ``"csv"``.
    """
    if path == "-":
        import sys

        text = sys.stdin.read()
        name = "<stdin>"
    else:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            raise ParseError(f"cannot read file: {exc.strerror or exc}", path) from exc
        name = path
    if fmt == "auto":
        fmt = sniff_format(name, text)
    if fmt == "csv":
        return parse_csv(text, name, a_key, b_key, winner_key)
    if fmt == "jsonl":
        return parse_jsonl(text.splitlines(), name, a_key, b_key, winner_key)
    raise ParseError(f"unknown input format {fmt!r} (use jsonl or csv)", name)

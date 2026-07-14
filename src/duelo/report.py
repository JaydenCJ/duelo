"""Rendering leaderboards, head-to-head matrices, and dataset summaries.

Four output formats share one column model:

* ``table`` — aligned plain text for terminals (the default),
* ``markdown`` — a pipe table ready to paste into a PR or doc,
* ``json`` — machine-readable, stable key order, includes all metadata,
* ``csv`` — one row per item for spreadsheets.

Numbers are formatted once, here, so every format shows identical values:
ratings to one decimal, win rates to one decimal percent.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Dict, List, Optional, Sequence, Tuple

from .dataset import Dataset
from .ranking import ItemRating, RankingResult

FORMATS = ("table", "markdown", "json", "csv")


def _fmt_rating(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.1f}"


def _fmt_ci(row: ItemRating) -> str:
    if row.ci_low is None or row.ci_high is None:
        return "-"
    return f"{row.ci_low:.1f} .. {row.ci_high:.1f}"


def _fmt_pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _leaderboard_cells(result: RankingResult) -> Tuple[List[str], List[List[str]]]:
    ci_header = f"{result.level:.0%} CI"
    header = ["rank", "item", "rating", ci_header, "games", "wins", "losses", "ties", "win%"]
    rows = []
    for rank, row in enumerate(result.items, start=1):
        rows.append(
            [
                str(rank),
                row.name,
                _fmt_rating(row.rating),
                _fmt_ci(row),
                str(row.games),
                str(row.wins),
                str(row.losses),
                str(row.ties),
                _fmt_pct(row.win_rate),
            ]
        )
    return header, rows


def _align_table(header: List[str], rows: List[List[str]], numeric: Sequence[int]) -> str:
    widths = [len(h) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def render_row(cells: List[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            if i in numeric:
                parts.append(cell.rjust(widths[i]))
            else:
                parts.append(cell.ljust(widths[i]))
        return "  ".join(parts).rstrip()

    lines = [render_row(header)]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def _markdown_table(header: List[str], rows: List[List[str]], numeric: Sequence[int]) -> str:
    def escape(cell: str) -> str:
        return cell.replace("|", "\\|")

    lines = ["| " + " | ".join(escape(h) for h in header) + " |"]
    seps = ["---:" if i in numeric else "---" for i in range(len(header))]
    lines.append("| " + " | ".join(seps) + " |")
    for row in rows:
        lines.append("| " + " | ".join(escape(c) for c in row) + " |")
    return "\n".join(lines)


def render_leaderboard(result: RankingResult, fmt: str = "table") -> str:
    """Render a :class:`RankingResult` in one of :data:`FORMATS`."""
    header, rows = _leaderboard_cells(result)
    numeric = (0, 2, 3, 4, 5, 6, 7, 8)
    if fmt == "table":
        title = (
            f"{result.method} leaderboard - {result.n_battles} battles, "
            f"{result.n_ties} ties, ci={result.ci_method}"
        )
        return title + "\n" + _align_table(header, rows, numeric)
    if fmt == "markdown":
        return _markdown_table(header, rows, numeric)
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        return buf.getvalue().rstrip("\n")
    if fmt == "json":
        payload = {
            "method": result.method,
            "n_battles": result.n_battles,
            "n_ties": result.n_ties,
            "ci": {"method": result.ci_method, "level": result.level},
            "meta": result.meta,
            "items": [
                {
                    "rank": rank,
                    "name": row.name,
                    "rating": round(row.rating, 4),
                    "ci_low": None if row.ci_low is None else round(row.ci_low, 4),
                    "ci_high": None if row.ci_high is None else round(row.ci_high, 4),
                    "games": row.games,
                    "wins": row.wins,
                    "losses": row.losses,
                    "ties": row.ties,
                    "win_rate": round(row.win_rate, 4),
                }
                for rank, row in enumerate(result.items, start=1)
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)
    raise ValueError(f"unknown output format {fmt!r} (use {', '.join(FORMATS)})")


# -- head-to-head matrix ---------------------------------------------------


def head_to_head(dataset: Dataset) -> Dict[Tuple[str, str], Tuple[int, int, int]]:
    """Per ordered pair (row, col): (row wins, row losses, ties)."""
    cells: Dict[Tuple[str, str], Tuple[int, int, int]] = {}
    for (first, second), stats in dataset.pairs.items():
        total_games = int(round(stats.games))
        ties_count = int(round(stats.ties))
        decisive_first = int(round(stats.wins_first - 0.5 * stats.ties))
        decisive_second = total_games - ties_count - decisive_first
        cells[(first, second)] = (decisive_first, decisive_second, ties_count)
        cells[(second, first)] = (decisive_second, decisive_first, ties_count)
    return cells


def render_matrix(dataset: Dataset, fmt: str = "table") -> str:
    """Render the win/loss/tie matrix. Cell = ``W-L-T`` from the row's view."""
    items = dataset.items
    cells = head_to_head(dataset)
    header = ["item"] + items
    rows: List[List[str]] = []
    for row_name in items:
        row = [row_name]
        for col_name in items:
            if row_name == col_name:
                row.append("-")
            elif (row_name, col_name) in cells:
                w, l, t = cells[(row_name, col_name)]
                row.append(f"{w}-{l}-{t}")
            else:
                row.append(".")
        rows.append(row)
    numeric = tuple(range(1, len(header)))
    if fmt == "table":
        title = f"head-to-head (row vs column, W-L-T) - {dataset.n_battles} battles"
        return title + "\n" + _align_table(header, rows, numeric)
    if fmt == "markdown":
        return _markdown_table(header, rows, numeric)
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        return buf.getvalue().rstrip("\n")
    if fmt == "json":
        payload = {
            "items": items,
            "n_battles": dataset.n_battles,
            "cells": [
                {"a": a, "b": b, "wins": w, "losses": l, "ties": t}
                for (a, b), (w, l, t) in sorted(cells.items())
                if a < b
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)
    raise ValueError(f"unknown output format {fmt!r} (use {', '.join(FORMATS)})")


# -- dataset summary ---------------------------------------------------------


def render_stats(dataset: Dataset, fmt: str = "table") -> str:
    """Summarize a battle log: volume, coverage, and fit health."""
    m = len(dataset.items)
    observed_pairs = sum(1 for s in dataset.pairs.values() if s.games > 0)
    possible_pairs = m * (m - 1) // 2
    components = dataset.components()
    degenerate = dataset.degenerate_items()
    if fmt == "json":
        payload = {
            "battles": dataset.n_battles,
            "ties": dataset.n_ties,
            "items": m,
            "pairs_observed": observed_pairs,
            "pairs_possible": possible_pairs,
            "components": components,
            "degenerate_items": degenerate,
            "per_item": [
                {
                    "name": name,
                    "games": dataset.raw_wins.get(name, 0)
                    + dataset.raw_losses.get(name, 0)
                    + dataset.raw_ties.get(name, 0),
                    "wins": dataset.raw_wins.get(name, 0),
                    "losses": dataset.raw_losses.get(name, 0),
                    "ties": dataset.raw_ties.get(name, 0),
                }
                for name in dataset.items
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    header = ["item", "games", "wins", "losses", "ties"]
    rows = []
    for name in dataset.items:
        wins = dataset.raw_wins.get(name, 0)
        losses = dataset.raw_losses.get(name, 0)
        ties = dataset.raw_ties.get(name, 0)
        rows.append([name, str(wins + losses + ties), str(wins), str(losses), str(ties)])
    if fmt == "csv":
        # CSV carries the per-item table; the full summary (coverage,
        # components, degeneracy) is available via --format json.
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        return buf.getvalue().rstrip("\n")
    if fmt not in ("table", "markdown"):
        raise ValueError(f"unknown output format {fmt!r} (use {', '.join(FORMATS)})")
    lines = [
        f"battles:     {dataset.n_battles}",
        f"ties:        {dataset.n_ties}",
        f"items:       {m}",
        f"pair coverage: {observed_pairs}/{possible_pairs} observed",
        f"components:  {len(components)}"
        + ("" if len(components) <= 1 else "  (DISCONNECTED - Bradley-Terry needs --prior)"),
    ]
    if degenerate:
        lines.append(
            "degenerate:  " + ", ".join(degenerate) + "  (all wins or all losses - needs --prior)"
        )
    else:
        lines.append("degenerate:  none")
    body = _align_table(header, rows, numeric=(1, 2, 3, 4))
    if fmt == "markdown":
        body = _markdown_table(header, rows, numeric=(1, 2, 3, 4))
    return "\n".join(lines) + "\n\n" + body

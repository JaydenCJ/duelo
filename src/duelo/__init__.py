"""duelo — Bradley-Terry and Elo rankings with confidence intervals from
pairwise preference logs.

Typical library use:

    from duelo import load_battles, rank_bradley_terry

    battles = load_battles("battles.jsonl")
    board = rank_bradley_terry(battles, ci="bootstrap", seed=7)
    for row in board.items:
        print(row.name, round(row.rating, 1), row.ci_low, row.ci_high)

Everything is pure standard library and fully offline.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .bootstrap import (
    BootstrapResult,
    bootstrap_bradley_terry,
    bootstrap_elo,
)
from .bradley_terry import BTFit, fit as fit_bradley_terry
from .dataset import Dataset, PairStats, build_dataset
from .elo import EloResult, expected_score, run_elo
from .errors import DegenerateDataError, DisconnectedError, DueloError, ParseError
from .ranking import (
    ItemRating,
    RankingResult,
    beta_to_rating,
    rank_bradley_terry,
    rank_elo,
)
from .records import Battle, load_battles, normalize_winner
from .report import render_leaderboard, render_matrix, render_stats

__all__ = [
    "__version__",
    "Battle",
    "BootstrapResult",
    "BTFit",
    "Dataset",
    "DegenerateDataError",
    "DisconnectedError",
    "DueloError",
    "EloResult",
    "ItemRating",
    "PairStats",
    "ParseError",
    "RankingResult",
    "beta_to_rating",
    "bootstrap_bradley_terry",
    "bootstrap_elo",
    "build_dataset",
    "expected_score",
    "fit_bradley_terry",
    "load_battles",
    "normalize_winner",
    "rank_bradley_terry",
    "rank_elo",
    "render_leaderboard",
    "render_matrix",
    "render_stats",
    "run_elo",
]

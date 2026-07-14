"""Sequential Elo ratings over a battle log.

Elo is the online counterpart to Bradley-Terry: it processes games in
order, moving each player's rating by ``k * (score - expected)`` where
``expected = 1 / (1 + 10 ** ((r_b - r_a) / scale))``. Ties score 0.5.

Because updates are sequential, Elo ratings depend on game order and on the
K-factor — that is a feature when recency matters (a model was upgraded
mid-log) and a bug when it does not. duelo exposes both methods and the
README says when to prefer which. Uncertainty for Elo comes from the
bootstrap (there is no likelihood to differentiate); see
:mod:`duelo.bootstrap`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .records import Battle

DEFAULT_K = 32.0
DEFAULT_INITIAL = 1000.0
DEFAULT_SCALE = 400.0


def expected_score(rating_a: float, rating_b: float, scale: float = DEFAULT_SCALE) -> float:
    """Probability-like expected score of A against B under the Elo curve."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / scale))


@dataclass
class EloResult:
    """Final ratings plus per-item game counts after a sequential pass."""

    ratings: Dict[str, float]
    games: Dict[str, int] = field(default_factory=dict)
    k: float = DEFAULT_K
    initial: float = DEFAULT_INITIAL
    scale: float = DEFAULT_SCALE

    def rating_of(self, item: str) -> float:
        return self.ratings[item]


def run_elo(
    battles: Sequence[Battle],
    k: float = DEFAULT_K,
    initial: float = DEFAULT_INITIAL,
    scale: float = DEFAULT_SCALE,
) -> EloResult:
    """Run one sequential Elo pass over ``battles`` in the given order."""
    if k <= 0:
        raise ValueError("k must be > 0")
    if scale <= 0:
        raise ValueError("scale must be > 0")
    ratings: Dict[str, float] = {}
    games: Dict[str, int] = {}
    for battle in battles:
        ra = ratings.get(battle.a, initial)
        rb = ratings.get(battle.b, initial)
        ea = expected_score(ra, rb, scale)
        if battle.outcome == "a":
            score_a = 1.0
        elif battle.outcome == "b":
            score_a = 0.0
        else:
            score_a = 0.5
        delta = k * (score_a - ea)
        ratings[battle.a] = ra + delta
        ratings[battle.b] = rb - delta
        games[battle.a] = games.get(battle.a, 0) + 1
        games[battle.b] = games.get(battle.b, 0) + 1
    return EloResult(ratings=ratings, games=games, k=k, initial=initial, scale=scale)


def elo_ratings_vector(result: EloResult, items: List[str]) -> List[float]:
    """Ratings aligned with ``items``; unseen items get the initial rating."""
    return [result.ratings.get(item, result.initial) for item in items]

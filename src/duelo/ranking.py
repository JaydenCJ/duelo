"""High-level ranking API: battles in, rated leaderboard out.

This module glues parsing, fitting, and uncertainty into one call per
method and converts everything onto a familiar Elo-like display scale:

    rating_i = base + scale * log10(strength_i / geometric_mean_strength)

With the defaults (base 1000, scale 400) a 100-point gap means roughly a
64% win probability, and 200 points roughly 76% — the same intuition as
chess Elo. Confidence intervals are attached per item, either analytic
(Wald, from the Fisher information; Bradley-Terry only) or bootstrap
percentile (both methods).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Dict, List, Optional, Sequence

from . import bootstrap as bootstrap_mod
from . import bradley_terry
from .dataset import Dataset, build_dataset
from .elo import DEFAULT_INITIAL, DEFAULT_K, elo_ratings_vector, run_elo
from .records import Battle

DEFAULT_BASE = 1000.0
DEFAULT_SCALE = 400.0

CI_ANALYTIC = "analytic"
CI_BOOTSTRAP = "bootstrap"
CI_NONE = "none"

_LN10 = math.log(10.0)


@dataclass
class ItemRating:
    """One leaderboard row. ``ci_low``/``ci_high`` are None when ci='none'."""

    name: str
    rating: float
    ci_low: Optional[float]
    ci_high: Optional[float]
    games: int
    wins: int
    losses: int
    ties: int

    @property
    def win_rate(self) -> float:
        """Win share with ties counted as half, in [0, 1]."""
        if self.games == 0:
            return 0.0
        return (self.wins + 0.5 * self.ties) / self.games


@dataclass
class RankingResult:
    """A full leaderboard: rows sorted by rating (descending) plus metadata."""

    method: str
    items: List[ItemRating]
    n_battles: int
    n_ties: int
    ci_method: str
    level: float
    meta: Dict[str, object] = field(default_factory=dict)

    def rating_of(self, name: str) -> ItemRating:
        for item in self.items:
            if item.name == name:
                return item
        raise KeyError(name)

    def names(self) -> List[str]:
        return [item.name for item in self.items]


def beta_to_rating(beta: float, base: float = DEFAULT_BASE, scale: float = DEFAULT_SCALE) -> float:
    """Map a centered natural-log strength onto the display scale."""
    return base + scale * beta / _LN10


def _counts(dataset: Dataset, name: str) -> Dict[str, int]:
    wins = dataset.raw_wins.get(name, 0)
    losses = dataset.raw_losses.get(name, 0)
    ties = dataset.raw_ties.get(name, 0)
    return {"games": wins + losses + ties, "wins": wins, "losses": losses, "ties": ties}


def _sorted_rows(rows: List[ItemRating]) -> List[ItemRating]:
    return sorted(rows, key=lambda r: (-r.rating, r.name))


def rank_bradley_terry(
    battles: Sequence[Battle],
    prior: float = 0.0,
    base: float = DEFAULT_BASE,
    scale: float = DEFAULT_SCALE,
    ci: str = CI_ANALYTIC,
    level: float = 0.95,
    rounds: int = bootstrap_mod.DEFAULT_ROUNDS,
    seed: int = bootstrap_mod.DEFAULT_SEED,
) -> RankingResult:
    """Bradley-Terry leaderboard with confidence intervals.

    ``ci`` is ``"analytic"`` (Wald interval from the Fisher information,
    the default), ``"bootstrap"`` (percentile, ``rounds`` resamples,
    deterministic under ``seed``), or ``"none"``.
    """
    if ci not in (CI_ANALYTIC, CI_BOOTSTRAP, CI_NONE):
        raise ValueError(f"unknown ci method {ci!r}")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    dataset = build_dataset(battles)
    fit = bradley_terry.fit(dataset, prior=prior)
    factor = scale / _LN10

    lows: List[Optional[float]] = [None] * len(fit.items)
    highs: List[Optional[float]] = [None] * len(fit.items)
    if ci == CI_ANALYTIC:
        z = NormalDist().inv_cdf(0.5 + level / 2.0)
        errors = bradley_terry.standard_errors(dataset, fit)
        for i, (beta, se) in enumerate(zip(fit.beta, errors)):
            center = beta_to_rating(beta, base, scale)
            lows[i] = center - z * se * factor
            highs[i] = center + z * se * factor
    elif ci == CI_BOOTSTRAP:
        boot = bootstrap_mod.bootstrap_bradley_terry(
            battles, fit.items, prior=prior, rounds=rounds, seed=seed, level=level
        )
        lows = [beta_to_rating(v, base, scale) for v in boot.lows]
        highs = [beta_to_rating(v, base, scale) for v in boot.highs]

    rows = []
    for i, name in enumerate(fit.items):
        counts = _counts(dataset, name)
        rows.append(
            ItemRating(
                name=name,
                rating=beta_to_rating(fit.beta[i], base, scale),
                ci_low=lows[i],
                ci_high=highs[i],
                **counts,
            )
        )
    meta: Dict[str, object] = {
        "base": base,
        "scale": scale,
        "prior": prior,
        "iterations": fit.iterations,
        "converged": fit.converged,
    }
    if ci == CI_BOOTSTRAP:
        meta.update({"rounds": rounds, "seed": seed})
    return RankingResult(
        method="bradley-terry",
        items=_sorted_rows(rows),
        n_battles=dataset.n_battles,
        n_ties=dataset.n_ties,
        ci_method=ci,
        level=level,
        meta=meta,
    )


def rank_elo(
    battles: Sequence[Battle],
    k: float = DEFAULT_K,
    initial: float = DEFAULT_INITIAL,
    scale: float = DEFAULT_SCALE,
    ci: str = CI_BOOTSTRAP,
    level: float = 0.95,
    rounds: int = bootstrap_mod.DEFAULT_ROUNDS,
    seed: int = bootstrap_mod.DEFAULT_SEED,
) -> RankingResult:
    """Sequential Elo leaderboard; CIs via bootstrap (or ``"none"``).

    There is no analytic interval for sequential Elo — it is an update
    rule, not a likelihood — so requesting ``ci="analytic"`` is an error
    rather than a silently different answer.
    """
    if ci == CI_ANALYTIC:
        raise ValueError(
            "Elo has no analytic confidence interval; use ci='bootstrap' or 'none'"
        )
    if ci not in (CI_BOOTSTRAP, CI_NONE):
        raise ValueError(f"unknown ci method {ci!r}")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    dataset = build_dataset(battles)
    result = run_elo(battles, k=k, initial=initial, scale=scale)
    items = dataset.items
    ratings = elo_ratings_vector(result, items)

    lows: List[Optional[float]] = [None] * len(items)
    highs: List[Optional[float]] = [None] * len(items)
    if ci == CI_BOOTSTRAP:
        boot = bootstrap_mod.bootstrap_elo(
            battles,
            items,
            k=k,
            initial=initial,
            scale=scale,
            rounds=rounds,
            seed=seed,
            level=level,
        )
        lows = list(boot.lows)
        highs = list(boot.highs)

    rows = []
    for i, name in enumerate(items):
        counts = _counts(dataset, name)
        rows.append(
            ItemRating(
                name=name,
                rating=ratings[i],
                ci_low=lows[i],
                ci_high=highs[i],
                **counts,
            )
        )
    meta: Dict[str, object] = {"k": k, "initial": initial, "scale": scale}
    if ci == CI_BOOTSTRAP:
        meta.update({"rounds": rounds, "seed": seed})
    return RankingResult(
        method="elo",
        items=_sorted_rows(rows),
        n_battles=dataset.n_battles,
        n_ties=dataset.n_ties,
        ci_method=ci,
        level=level,
        meta=meta,
    )

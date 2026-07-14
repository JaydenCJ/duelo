"""Bootstrap confidence intervals for both ranking methods.

The nonparametric bootstrap resamples the battle log with replacement
``rounds`` times, refits the ranking on each resample, and takes percentile
intervals of each item's rating — the same procedure arena-style
leaderboards use. It makes no normality assumption, so it captures the
asymmetric uncertainty of lopsided records that the analytic (Wald)
interval smooths over.

Everything is deterministic: draws come from ``random.Random(seed)`` and
nothing depends on wall-clock or hash order. A resample can be *degenerate*
for Bradley-Terry (an item vanishes or wins everything even though the full
log is fine), so BT refits add a tiny smoothing prior
(``BOOTSTRAP_MIN_PRIOR``) when the user's own prior is smaller — documented
in ``docs/methodology.md`` and surfaced in the result metadata.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, List, Sequence

from . import bradley_terry
from .dataset import build_dataset
from .elo import DEFAULT_INITIAL, DEFAULT_K, DEFAULT_SCALE, elo_ratings_vector, run_elo
from .records import Battle

DEFAULT_ROUNDS = 200
DEFAULT_SEED = 42
# Smallest smoothing prior applied inside BT bootstrap refits so degenerate
# resamples stay fittable. Small enough to leave ratings unchanged at
# reporting precision on any realistic log.
BOOTSTRAP_MIN_PRIOR = 1e-6


@dataclass
class BootstrapResult:
    """Percentile bounds per item (aligned with ``items``) plus metadata."""

    items: List[str]
    lows: List[float]
    highs: List[float]
    rounds: int
    seed: int
    level: float


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile of pre-sorted values, q in [0, 1]."""
    if not sorted_values:
        raise ValueError("cannot take a percentile of no values")
    if q < 0 or q > 1:
        raise ValueError("q must be within [0, 1]")
    pos = q * (len(sorted_values) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def _resample(battles: Sequence[Battle], rng: random.Random) -> List[Battle]:
    n = len(battles)
    return [battles[rng.randrange(n)] for _ in range(n)]


def _bootstrap(
    battles: Sequence[Battle],
    items: List[str],
    refit: Callable[[List[Battle]], List[float]],
    rounds: int,
    seed: int,
    level: float,
) -> BootstrapResult:
    if not battles:
        raise ValueError("cannot bootstrap an empty battle list")
    if rounds < 2:
        raise ValueError("bootstrap needs at least 2 rounds")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    rng = random.Random(seed)
    samples: List[List[float]] = [[] for _ in items]
    for _ in range(rounds):
        ratings = refit(_resample(battles, rng))
        for i, value in enumerate(ratings):
            samples[i].append(value)
    alpha = (1.0 - level) / 2.0
    lows, highs = [], []
    for values in samples:
        values.sort()
        lows.append(percentile(values, alpha))
        highs.append(percentile(values, 1.0 - alpha))
    return BootstrapResult(
        items=list(items), lows=lows, highs=highs, rounds=rounds, seed=seed, level=level
    )


def bootstrap_bradley_terry(
    battles: Sequence[Battle],
    items: List[str],
    prior: float = 0.0,
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
    level: float = 0.95,
) -> BootstrapResult:
    """Percentile CIs of centered BT log-strengths (natural-log units).

    Every refit includes all ``items`` (via the smoothing prior's pseudo-
    ties), so an item missing from one resample simply contributes a
    near-average draw rather than crashing the round.
    """
    effective_prior = max(prior, BOOTSTRAP_MIN_PRIOR)
    all_items = list(items)

    def refit(sample: List[Battle]) -> List[float]:
        data = build_dataset(sample)
        # Ensure every item participates so vectors stay aligned.
        missing = [name for name in all_items if name not in data.items]
        if missing:
            data.items = sorted(data.items + missing)
        fit = bradley_terry.fit(data, prior=effective_prior)
        return [fit.beta_of(name) for name in all_items]

    return _bootstrap(battles, all_items, refit, rounds, seed, level)


def bootstrap_elo(
    battles: Sequence[Battle],
    items: List[str],
    k: float = DEFAULT_K,
    initial: float = DEFAULT_INITIAL,
    scale: float = DEFAULT_SCALE,
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
    level: float = 0.95,
) -> BootstrapResult:
    """Percentile CIs of sequential Elo ratings (rating-scale units).

    Each resample is replayed in its sampled order, so the interval also
    absorbs Elo's order sensitivity — expect it to be wider than BT's.
    """

    def refit(sample: List[Battle]) -> List[float]:
        result = run_elo(sample, k=k, initial=initial, scale=scale)
        return elo_ratings_vector(result, items)

    return _bootstrap(battles, list(items), refit, rounds, seed, level)

"""Bootstrap CIs: determinism under a seed, interval sanity, degenerate
resamples, and the percentile helper."""

from __future__ import annotations

import pytest

from duelo.bootstrap import (
    bootstrap_bradley_terry,
    bootstrap_elo,
    percentile,
)
from duelo.dataset import build_dataset
from duelo import bradley_terry
from conftest import simulate_battles, ties, wins


def test_percentile_interpolates_linearly_and_rejects_bad_input():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0.0) == 10.0
    assert percentile(values, 1.0) == 40.0
    assert percentile(values, 0.5) == pytest.approx(25.0)
    with pytest.raises(ValueError, match="no values"):
        percentile([], 0.5)
    with pytest.raises(ValueError, match="within"):
        percentile([1.0], 1.5)


def test_same_seed_identical_intervals_different_seed_different(arena_log):
    items = build_dataset(arena_log).items
    a = bootstrap_bradley_terry(arena_log, items, rounds=50, seed=3)
    b = bootstrap_bradley_terry(arena_log, items, rounds=50, seed=3)
    assert a.lows == b.lows and a.highs == b.highs
    c = bootstrap_bradley_terry(arena_log, items, rounds=50, seed=4)
    assert a.lows != c.lows


def test_interval_brackets_the_full_fit_estimate(arena_log):
    data = build_dataset(arena_log)
    fit = bradley_terry.fit(data)
    boot = bootstrap_bradley_terry(arena_log, data.items, rounds=200, seed=42)
    for i, name in enumerate(boot.items):
        assert boot.lows[i] <= fit.beta_of(name) <= boot.highs[i]


def test_more_data_narrows_the_interval():
    true_beta = {"x": 0.4, "y": -0.4}
    small = simulate_battles(true_beta, 40, seed=5)
    large = simulate_battles(true_beta, 4000, seed=5)
    b_small = bootstrap_bradley_terry(small, ["x", "y"], rounds=80, seed=9)
    b_large = bootstrap_bradley_terry(large, ["x", "y"], rounds=80, seed=9)
    width = lambda b: b.highs[0] - b.lows[0]  # noqa: E731
    assert width(b_large) < width(b_small) / 3


def test_degenerate_resamples_do_not_crash_bt_bootstrap():
    # "rare" wins exactly once in 40 battles; many resamples will drop that
    # win entirely, making the resample degenerate. The smoothing prior must
    # keep every round fittable.
    battles = wins("a", "b", 20) + wins("b", "a", 19) + wins("rare", "a", 1)
    items = ["a", "b", "rare"]
    boot = bootstrap_bradley_terry(battles, items, rounds=60, seed=4)
    assert len(boot.lows) == 3
    assert all(low <= high for low, high in zip(boot.lows, boot.highs))


def test_bt_bootstrap_respects_user_prior_over_minimum():
    battles = wins("a", "b", 6) + wins("b", "a", 2)
    tight = bootstrap_bradley_terry(battles, ["a", "b"], prior=5.0, rounds=60, seed=8)
    loose = bootstrap_bradley_terry(battles, ["a", "b"], prior=0.0, rounds=60, seed=8)
    # A heavy prior shrinks everything toward zero, so bounds sit closer to 0.
    assert abs(tight.highs[0]) < abs(loose.highs[0])


def test_elo_bootstrap_is_deterministic_and_ordered(arena_log):
    data = build_dataset(arena_log)
    a = bootstrap_elo(arena_log, data.items, rounds=50, seed=13)
    b = bootstrap_elo(arena_log, data.items, rounds=50, seed=13)
    assert a.lows == b.lows and a.highs == b.highs
    assert all(low <= high for low, high in zip(a.lows, a.highs))


def test_bootstrap_validates_rounds_level_and_empty_log():
    battles = ties("a", "b", 2)
    with pytest.raises(ValueError, match="at least 2 rounds"):
        bootstrap_bradley_terry(battles, ["a", "b"], rounds=1)
    with pytest.raises(ValueError, match="level"):
        bootstrap_bradley_terry(battles, ["a", "b"], level=1.0)
    with pytest.raises(ValueError, match="empty battle list"):
        bootstrap_elo([], ["a", "b"])

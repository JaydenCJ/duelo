"""The high-level ranking API: display scale, CI wiring, sorting, metadata."""

from __future__ import annotations

import math

import pytest

from duelo.ranking import (
    beta_to_rating,
    rank_bradley_terry,
    rank_elo,
)
from conftest import ties, wins


def test_beta_to_rating_scale_anchors():
    assert beta_to_rating(0.0) == 1000.0
    # A 10x strength advantage (ln 10 nats) is worth `scale` points.
    assert beta_to_rating(math.log(10.0)) == pytest.approx(1400.0)
    assert beta_to_rating(math.log(10.0), base=1500.0, scale=100.0) == pytest.approx(1600.0)


def test_leaderboard_sorted_by_rating_descending(arena_log):
    board = rank_bradley_terry(arena_log)
    ratings = [row.rating for row in board.items]
    assert ratings == sorted(ratings, reverse=True)
    assert board.names()[0] == "alpha"


def test_analytic_ci_symmetric_and_wider_at_higher_level(arena_log):
    board = rank_bradley_terry(arena_log, ci="analytic", level=0.95)
    for row in board.items:
        assert row.ci_low is not None and row.ci_high is not None
        below = row.rating - row.ci_low
        above = row.ci_high - row.rating
        assert below == pytest.approx(above, rel=1e-9)
        assert below > 0
    narrow = rank_bradley_terry(arena_log, level=0.80).items[0]
    wide = rank_bradley_terry(arena_log, level=0.99).items[0]
    assert (wide.ci_high - wide.ci_low) > (narrow.ci_high - narrow.ci_low)


def test_ci_none_unsets_bounds_and_bootstrap_records_metadata(arena_log):
    board = rank_bradley_terry(arena_log, ci="none")
    assert all(row.ci_low is None and row.ci_high is None for row in board.items)
    boot = rank_bradley_terry(arena_log, ci="bootstrap", rounds=50, seed=5)
    assert boot.meta["rounds"] == 50
    assert boot.meta["seed"] == 5
    assert boot.ci_method == "bootstrap"


def test_bootstrap_and_analytic_agree_roughly(arena_log):
    analytic = rank_bradley_terry(arena_log, ci="analytic")
    boot = rank_bradley_terry(arena_log, ci="bootstrap", rounds=200, seed=42)
    for name in analytic.names():
        a = analytic.rating_of(name)
        b = boot.rating_of(name)
        width_a = a.ci_high - a.ci_low
        width_b = b.ci_high - b.ci_low
        # Same order of magnitude: within a factor of two of each other.
        assert 0.5 < width_a / width_b < 2.0


def test_win_rate_counts_ties_as_half():
    board = rank_bradley_terry(
        wins("a", "b", 2) + wins("b", "a", 1) + ties("a", "b", 1), ci="none"
    )
    row = board.rating_of("a")
    assert row.games == 4
    assert row.win_rate == pytest.approx((2 + 0.5) / 4)


def test_elo_rejects_analytic_ci_with_clear_message(arena_log):
    with pytest.raises(ValueError, match="no analytic confidence interval"):
        rank_elo(arena_log, ci="analytic")


def test_elo_leaderboard_matches_sequential_run(arena_log):
    board = rank_elo(arena_log, ci="none", k=24, initial=1200.0)
    assert board.method == "elo"
    assert board.meta["k"] == 24
    total = sum(row.rating for row in board.items)
    assert total == pytest.approx(len(board.items) * 1200.0)


def test_unknown_ci_bad_level_and_unknown_item_rejected(arena_log):
    with pytest.raises(ValueError, match="unknown ci"):
        rank_bradley_terry(arena_log, ci="magic")
    with pytest.raises(ValueError, match="level"):
        rank_elo(arena_log, level=2.0)
    board = rank_bradley_terry(arena_log, ci="none")
    with pytest.raises(KeyError):
        board.rating_of("nonexistent")

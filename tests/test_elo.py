"""Sequential Elo: update arithmetic, zero-sum invariant, order dependence."""

from __future__ import annotations

import pytest

from duelo.elo import elo_ratings_vector, expected_score, run_elo
from conftest import battle, ties, wins


def test_first_game_between_equals_moves_half_k_and_tie_moves_nothing():
    result = run_elo(wins("a", "b", 1), k=32)
    assert result.ratings["a"] == pytest.approx(1016.0)
    assert result.ratings["b"] == pytest.approx(984.0)
    tied = run_elo(ties("a", "b", 1))
    assert tied.ratings["a"] == pytest.approx(1000.0)
    assert tied.ratings["b"] == pytest.approx(1000.0)


def test_expected_score_matches_elo_curve_and_both_sides_sum_to_one():
    # 400 points of advantage on the default scale = 10:1 odds.
    assert expected_score(1400, 1000) == pytest.approx(10.0 / 11.0)
    assert expected_score(1000, 1000) == pytest.approx(0.5)
    assert expected_score(1234, 987) + expected_score(987, 1234) == pytest.approx(1.0)


def test_upset_win_moves_more_points_than_expected_win():
    # b (underdog after losing twice) then beats a: the swing is > half K.
    warmup = wins("a", "b", 2)
    upset = run_elo(warmup + wins("b", "a", 1), k=32)
    expected_only = run_elo(warmup, k=32)
    swing = upset.ratings["b"] - expected_only.ratings["b"]
    assert swing > 16.0


def test_updates_are_zero_sum_and_games_are_counted():
    log = wins("a", "b", 3) + wins("b", "c", 2) + ties("c", "a", 2) + wins("c", "b", 1)
    result = run_elo(log, initial=1000.0)
    assert sum(result.ratings.values()) == pytest.approx(3 * 1000.0)
    assert result.games == {"a": 5, "b": 6, "c": 5}


def test_elo_depends_on_game_order_bradley_terry_does_not():
    # Same multiset of games, different order -> different Elo endpoint.
    forward = wins("a", "b", 3) + wins("b", "a", 3) + wins("a", "b", 1)
    backward = wins("a", "b", 1) + wins("b", "a", 3) + wins("a", "b", 3)
    assert run_elo(forward).ratings["a"] != pytest.approx(run_elo(backward).ratings["a"])


def test_k_factor_scales_update_size():
    small_k = run_elo(wins("a", "b", 1), k=16).ratings["a"]
    large_k = run_elo(wins("a", "b", 1), k=64).ratings["a"]
    assert large_k - 1000.0 == pytest.approx(4 * (small_k - 1000.0))


def test_ratings_vector_falls_back_to_initial_for_unseen_items():
    result = run_elo(wins("a", "b", 1), initial=1200.0)
    vec = elo_ratings_vector(result, ["a", "b", "ghost"])
    assert vec[2] == 1200.0


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError, match="k must be"):
        run_elo([battle("a", "b", "a")], k=0)
    with pytest.raises(ValueError, match="scale must be"):
        run_elo([battle("a", "b", "a")], scale=-1)

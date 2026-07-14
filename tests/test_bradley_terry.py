"""Bradley-Terry fit: closed-form checks, invariances, degeneracy handling,
and the analytic uncertainty (Fisher information -> standard errors)."""

from __future__ import annotations

import math
import random

import pytest

from duelo import bradley_terry
from duelo.dataset import build_dataset
from duelo.errors import DegenerateDataError, DisconnectedError
from conftest import ties, wins


def fit_of(battles, **kwargs):
    return bradley_terry.fit(build_dataset(battles), **kwargs)


def test_two_items_mle_matches_closed_form_and_is_centered():
    # With two items the MLE ratio is exactly wins_a / wins_b: 3:1 here.
    fit = fit_of(wins("a", "b", 3) + wins("b", "a", 1))
    assert fit.beta_of("a") - fit.beta_of("b") == pytest.approx(math.log(3.0), abs=1e-9)
    assert sum(fit.beta) == pytest.approx(0.0, abs=1e-12)


def test_perfectly_balanced_record_gives_equal_strengths():
    fit = fit_of(wins("a", "b", 5) + wins("b", "a", 5))
    assert fit.beta == pytest.approx([0.0, 0.0], abs=1e-9)


def test_ties_count_as_half_wins():
    # a: 1 win + 1 tie = 1.5; b: 0 + 0.5. Two-item MLE ratio = 3.
    fit = fit_of(wins("a", "b", 1) + ties("a", "b", 1))
    assert fit.beta_of("a") - fit.beta_of("b") == pytest.approx(math.log(3.0), abs=1e-9)


def test_fit_is_independent_of_battle_order(arena_log):
    shuffled = list(arena_log)
    random.Random(99).shuffle(shuffled)
    fit_a = bradley_terry.fit(build_dataset(arena_log))
    fit_b = bradley_terry.fit(build_dataset(shuffled))
    assert fit_a.beta == pytest.approx(fit_b.beta, abs=1e-9)


def test_recovers_true_ordering_and_strengths(arena_log):
    true_beta = {"alpha": 0.8, "bravo": 0.4, "charlie": 0.0, "delta": -0.4, "echo": -0.8}
    fit = bradley_terry.fit(build_dataset(arena_log))
    recovered_order = sorted(fit.items, key=fit.beta_of, reverse=True)
    assert recovered_order == ["alpha", "bravo", "charlie", "delta", "echo"]
    for name, beta in true_beta.items():
        # 500 battles over 5 items: expect recovery within ~0.25 nats.
        assert fit.beta_of(name) == pytest.approx(beta, abs=0.25)


def test_shutout_raises_with_hint_and_prior_repairs_it():
    with pytest.raises(DegenerateDataError, match="--prior"):
        fit_of(wins("champ", "chump", 10))
    fit = fit_of(wins("champ", "chump", 10), prior=0.5)
    assert fit.beta_of("champ") > fit.beta_of("chump")
    assert math.isfinite(fit.beta_of("champ"))


def test_degenerate_error_message_agrees_in_number():
    # A single shutout item must read "1 item ... its", never "1 items".
    battles = wins("a", "b", 3) + wins("b", "a", 3) + wins("a", "c", 2)
    with pytest.raises(DegenerateDataError, match=r"1 item won or lost every game \(c\); its"):
        fit_of(battles)


def test_disconnected_graph_raises_and_prior_repairs_it():
    battles = wins("a1", "a2", 3) + wins("a2", "a1", 1) + ties("b1", "b2", 2)
    with pytest.raises(DisconnectedError, match="2 disconnected components"):
        fit_of(battles)
    fit = fit_of(battles, prior=0.1)
    assert fit.converged
    assert len(fit.beta) == 4


def test_single_item_raises():
    with pytest.raises(DegenerateDataError, match="at least 2"):
        bradley_terry.fit(build_dataset([]))


def test_prior_shrinks_ratings_toward_zero():
    battles = wins("a", "b", 8) + wins("b", "a", 2)
    loose = fit_of(battles).beta_of("a")
    shrunk = fit_of(battles, prior=5.0).beta_of("a")
    assert 0 < shrunk < loose


def test_max_iter_cap_reports_not_converged(arena_log):
    fit = bradley_terry.fit(build_dataset(arena_log), max_iter=1)
    assert not fit.converged
    assert fit.iterations == 1


def test_win_probability_is_sigmoid_of_beta_difference():
    fit = fit_of(wins("a", "b", 3) + wins("b", "a", 1))
    assert fit.win_probability("a", "b") == pytest.approx(0.75, abs=1e-6)
    assert fit.win_probability("b", "a") == pytest.approx(0.25, abs=1e-6)


# -- analytic uncertainty ---------------------------------------------------


def test_balanced_two_item_standard_error_closed_form():
    # Balanced record, mu = 0.5: Var(c_i) = 1 / (4 * n * 0.25) = 1/n.
    n = 100
    data = build_dataset(wins("a", "b", n // 2) + wins("b", "a", n // 2))
    fit = bradley_terry.fit(data)
    errors = bradley_terry.standard_errors(data, fit)
    assert errors == pytest.approx([1.0 / math.sqrt(n)] * 2, rel=1e-9)


def test_standard_errors_shrink_with_more_games():
    small = build_dataset(wins("a", "b", 5) + wins("b", "a", 5))
    large = build_dataset(wins("a", "b", 500) + wins("b", "a", 500))
    se_small = bradley_terry.standard_errors(small, bradley_terry.fit(small))
    se_large = bradley_terry.standard_errors(large, bradley_terry.fit(large))
    assert se_large[0] < se_small[0] / 5


def test_covariance_is_symmetric_positive_diagonal_zero_row_sums(arena_log):
    # Centered ratings sum to zero identically, so Cov(c_i, sum_j c_j) = 0.
    data = build_dataset(arena_log)
    cov = bradley_terry.covariance(data, bradley_terry.fit(data))
    m = len(cov)
    for i in range(m):
        assert cov[i][i] > 0
        assert sum(cov[i]) == pytest.approx(0.0, abs=1e-9)
        for j in range(m):
            assert cov[i][j] == pytest.approx(cov[j][i], abs=1e-12)


def test_item_with_fewer_games_has_wider_error(arena_log):
    # Give one extra item only a handful of games; its SE must dominate.
    extra = (
        wins("zulu", "alpha", 1)
        + wins("alpha", "zulu", 2)
        + ties("zulu", "bravo", 1)
    )
    data = build_dataset(list(arena_log) + extra)
    fit = bradley_terry.fit(data)
    errors = dict(zip(fit.items, bradley_terry.standard_errors(data, fit)))
    assert errors["zulu"] > 2 * max(errors[i] for i in fit.items if i != "zulu")

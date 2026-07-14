"""Bradley-Terry maximum-likelihood fit with analytic standard errors.

The Bradley-Terry model says item *i* beats item *j* with probability
``p_i / (p_i + p_j)`` where ``p_i > 0`` is item *i*'s latent strength.
Unlike sequential Elo, the fit uses all games at once and is independent of
game order — the correct choice for an offline log.

Fitting uses Hunter's (2004) minorization-maximization (MM) update

    p_i  <-  W_i / sum_j n_ij / (p_i + p_j)

where ``W_i`` is item *i*'s (fractional) win count and ``n_ij`` the games
between *i* and *j*. Ties count as half a win per side, so ``W_i`` may be
fractional; the update is unchanged. Every iteration renormalizes to a zero
mean in log space (the model is invariant to a global rescaling).

Uncertainty comes from the observed Fisher information of the log-strengths
``beta_i = log p_i``. The information matrix is singular along the all-ones
direction (the same invariance), so we invert the reduced matrix with item 0
dropped and propagate to the *centered* parametrization
``c_i = beta_i - mean(beta)`` — the quantity actually reported — via the
delta method. See ``docs/methodology.md`` for the full derivation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from . import linalg
from .dataset import Dataset
from .errors import DegenerateDataError, DisconnectedError

DEFAULT_TOL = 1e-12
DEFAULT_MAX_ITER = 20000


@dataclass
class BTFit:
    """Result of a Bradley-Terry fit.

    ``beta`` holds centered log-strengths (mean zero), aligned with
    ``items``. ``converged`` is False only if ``max_iter`` was hit first.
    """

    items: List[str]
    beta: List[float]
    iterations: int
    converged: bool
    prior: float

    def beta_of(self, item: str) -> float:
        return self.beta[self.items.index(item)]

    def win_probability(self, a: str, b: str) -> float:
        """Model probability that ``a`` beats ``b`` (ties split evenly)."""
        diff = self.beta_of(a) - self.beta_of(b)
        return 1.0 / (1.0 + math.exp(-diff))


def _check_fittable(dataset: Dataset) -> None:
    if len(dataset.items) < 2:
        raise DegenerateDataError(
            f"need at least 2 distinct items, found {len(dataset.items)}"
        )
    if not dataset.is_connected():
        comps = dataset.components()
        summary = "; ".join(
            "{" + ", ".join(c[:4]) + (", ..." if len(c) > 4 else "") + "}" for c in comps
        )
        raise DisconnectedError(
            f"comparison graph has {len(comps)} disconnected components "
            f"({summary}); items in different components share no games, so "
            f"one common scale does not exist. Collect cross-component "
            f"battles or pass a prior > 0 (e.g. --prior 0.1)."
        )
    degenerate = dataset.degenerate_items()
    if degenerate:
        shown = ", ".join(degenerate[:6]) + (", ..." if len(degenerate) > 6 else "")
        noun, pronoun = ("item", "its") if len(degenerate) == 1 else ("items", "their")
        raise DegenerateDataError(
            f"{len(degenerate)} {noun} won or lost every game ({shown}); "
            f"{pronoun} maximum-likelihood rating is infinite. Collect more data "
            f"or pass a prior > 0 (e.g. --prior 0.1) to regularize."
        )


def fit(
    dataset: Dataset,
    prior: float = 0.0,
    tol: float = DEFAULT_TOL,
    max_iter: int = DEFAULT_MAX_ITER,
) -> BTFit:
    """Fit Bradley-Terry strengths by the MM algorithm.

    ``prior`` adds that many pseudo-ties to every pair before fitting
    (see :meth:`duelo.dataset.Dataset.with_prior`). Raises
    :class:`DegenerateDataError` / :class:`DisconnectedError` when the MLE
    does not exist and no prior is supplied to repair it.
    """
    data = dataset.with_prior(prior)
    _check_fittable(data)
    items = data.items
    index: Dict[str, int] = {name: i for i, name in enumerate(items)}
    m = len(items)

    # Neighbor lists: for each item, (other_index, games) pairs.
    neighbors: List[List[Tuple[int, float]]] = [[] for _ in range(m)]
    for (a, b), stats in data.pairs.items():
        if stats.games <= 0:
            continue
        ia, ib = index[a], index[b]
        neighbors[ia].append((ib, stats.games))
        neighbors[ib].append((ia, stats.games))
    wins = [data.wins_of(item) for item in items]

    p = [1.0] * m
    iterations = 0
    converged = False
    for iterations in range(1, max_iter + 1):
        new_p = []
        for i in range(m):
            denom = sum(n / (p[i] + p[j]) for j, n in neighbors[i])
            new_p.append(wins[i] / denom)
        # Renormalize: geometric mean 1 (mean-zero in log space).
        log_mean = sum(math.log(v) for v in new_p) / m
        scale = math.exp(-log_mean)
        new_p = [v * scale for v in new_p]
        delta = max(abs(math.log(new_p[i]) - math.log(p[i])) for i in range(m))
        p = new_p
        if delta < tol:
            converged = True
            break

    beta = [math.log(v) for v in p]
    mean = sum(beta) / m
    beta = [b - mean for b in beta]
    return BTFit(
        items=list(items),
        beta=beta,
        iterations=iterations,
        converged=converged,
        prior=data.prior,
    )


def fisher_information(dataset: Dataset, fit_result: BTFit) -> linalg.Matrix:
    """Observed Fisher information of the log-strengths ``beta``.

    For each pair with ``n`` games and win probability ``mu``, the pair
    contributes ``n * mu * (1 - mu)`` — the binomial information of a
    logistic comparison. (With fractional wins from ties the observed
    information keeps the same form: the second derivative of the weighted
    log-likelihood does not involve the win counts.)
    """
    data = dataset.with_prior(max(0.0, fit_result.prior - dataset.prior))
    items = fit_result.items
    index = {name: i for i, name in enumerate(items)}
    m = len(items)
    info = [[0.0] * m for _ in range(m)]
    for (a, b), stats in data.pairs.items():
        if stats.games <= 0:
            continue
        ia, ib = index[a], index[b]
        mu = 1.0 / (1.0 + math.exp(-(fit_result.beta[ia] - fit_result.beta[ib])))
        weight = stats.games * mu * (1.0 - mu)
        info[ia][ia] += weight
        info[ib][ib] += weight
        info[ia][ib] -= weight
        info[ib][ia] -= weight
    return info


def covariance(dataset: Dataset, fit_result: BTFit) -> linalg.Matrix:
    """Asymptotic covariance of the *centered* log-strengths.

    The full information matrix is singular (translation invariance), so we
    invert it with item 0 dropped — giving the covariance of the contrasts
    ``d_k = beta_k - beta_0`` — and map to centered coordinates
    ``c_i = beta_i - mean(beta) = sum_k A_ik d_k`` with
    ``A_ik = delta_ik - 1/m`` (row 0: ``A_0k = -1/m``).
    """
    info = fisher_information(dataset, fit_result)
    m = len(info)
    reduced = [[info[i][j] for j in range(1, m)] for i in range(1, m)]
    sigma_reduced = linalg.invert(reduced)  # cov of d_1..d_{m-1}

    cov = [[0.0] * m for _ in range(m)]
    # Rows of A restricted to columns 1..m-1 (d_0 == 0 identically).
    a_rows = []
    for i in range(m):
        row = [(-1.0 / m) + (1.0 if i == k else 0.0) for k in range(1, m)]
        a_rows.append(row)
    n = m - 1
    for i in range(m):
        for j in range(i, m):
            total = 0.0
            for r in range(n):
                ari = a_rows[i][r]
                if ari == 0.0:
                    continue
                srow = sigma_reduced[r]
                total += ari * sum(srow[s] * a_rows[j][s] for s in range(n))
            cov[i][j] = total
            cov[j][i] = total
    return cov


def standard_errors(dataset: Dataset, fit_result: BTFit) -> List[float]:
    """Standard error of each centered log-strength, aligned with items."""
    cov = covariance(dataset, fit_result)
    return [math.sqrt(max(0.0, cov[i][i])) for i in range(len(cov))]

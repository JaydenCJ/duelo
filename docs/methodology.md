# How duelo computes rankings and confidence intervals

This document is the math behind the CLI, in the order the code applies it.
Module references point at `src/duelo/`.

## 1. The Bradley-Terry model (`bradley_terry.py`)

Each item *i* has a latent strength `p_i > 0`, and

```
P(i beats j) = p_i / (p_i + p_j)
```

Ties are counted as half a win for each side (the standard arena
convention), so win counts may be fractional. The model is invariant to a
global rescaling of all strengths, so duelo works with *centered*
log-strengths `beta_i = log p_i` with `mean(beta) = 0`.

### Fitting: the MM algorithm

duelo uses Hunter's (2004) minorization-maximization update:

```
p_i  <-  W_i / sum_j ( n_ij / (p_i + p_j) )
```

where `W_i` is item *i*'s fractional win count and `n_ij` the number of
games between *i* and *j*. Each iteration renormalizes to geometric mean 1.
Iteration stops when the largest log-strength change drops below `1e-12`
(default cap: 20000 iterations). The update is monotone in the likelihood,
so convergence to the MLE is guaranteed whenever the MLE exists.

### When the MLE does not exist

Two failure modes, both detected before fitting:

* **Degeneracy** — an item won everything (or lost everything). Its MLE
  strength is `+inf` (or 0). duelo raises `DegenerateDataError`.
* **Disconnection** — the comparison graph splits into components with no
  games between them. No common scale exists. duelo raises
  `DisconnectedError`.

Both are repaired by `--prior t`, which adds `t` pseudo-ties between
*every* pair of items: each pair gains `t` games and `t/2` fractional wins
per side. This bounds every strength, connects the graph, and shrinks
ratings toward equality — the effect vanishes as real data grows. Typical
values are 0.1–1.0.

### Display scale

Reported ratings are Elo-like:

```
rating_i = base + scale * log10(p_i / geometric_mean(p))
```

Defaults `base=1000`, `scale=400`: a 100-point gap is ~64% win probability,
200 points is ~76%, 400 points is 10:1 odds — the familiar chess intuition.

## 2. Analytic confidence intervals (Wald)

The observed Fisher information of the log-strengths has entries built from
each pair's `n_ij * mu_ij * (1 - mu_ij)`, where `mu_ij` is the fitted win
probability. (With ties-as-half-wins the second derivative of the weighted
log-likelihood keeps exactly this form.)

The information matrix is singular along the all-ones direction (the same
rescaling invariance), so duelo:

1. drops item 0 and inverts the reduced matrix (`linalg.py`, Gauss-Jordan
   with partial pivoting — leaderboards are small, so O(m³) pure Python is
   plenty), giving the covariance of the contrasts `d_k = beta_k - beta_0`;
2. maps to centered coordinates via the delta method:
   `c_i = beta_i - mean(beta) = sum_k A_ik d_k` with `A_ik = 1[i=k] - 1/m`.

The interval is `rating_i ± z * SE_i * scale / ln(10)` with `z` the normal
quantile for the requested level. Wald intervals are symmetric and cheap;
they are accurate when every item has a healthy number of games.

## 3. Bootstrap confidence intervals (`bootstrap.py`)

The nonparametric bootstrap resamples the battle log with replacement
(default 200 rounds, seed 42 — fully deterministic), refits on each
resample, and takes percentile bounds per item. It captures the asymmetric
uncertainty of lopsided or small records that Wald smooths over, at the
cost of `rounds` refits.

One subtlety: a resample can be degenerate even when the full log is fine
(a rare item's only win may not be drawn). Bradley-Terry bootstrap refits
therefore apply a smoothing prior of `max(user_prior, 1e-6)` pseudo-ties,
which keeps every round fittable and every item present. At `1e-6` the
effect on reported ratings is far below display precision.

## 4. Sequential Elo (`elo.py`)

The classic online update, processing battles in log order:

```
expected_a = 1 / (1 + 10 ** ((r_b - r_a) / scale))
r_a += k * (score_a - expected_a);  r_b -= the same amount
```

with `score_a` in {1, 0.5, 0}. Elo depends on game order and on `k` —
useful when recency should matter (an item changed mid-log), misleading
when it should not. For a static log, prefer `duelo rank`. Elo has no
likelihood, hence no analytic interval; duelo offers bootstrap CIs, whose
width also absorbs the order sensitivity (each resample is replayed in its
sampled order).

## 5. References

* R. A. Bradley and M. E. Terry (1952). "Rank Analysis of Incomplete Block
  Designs: I. The Method of Paired Comparisons." *Biometrika* 39.
* D. R. Hunter (2004). "MM algorithms for generalized Bradley-Terry
  models." *Annals of Statistics* 32(1).
* A. E. Elo (1978). *The Rating of Chessplayers, Past and Present.*
* B. Efron and R. Tibshirani (1993). *An Introduction to the Bootstrap.*

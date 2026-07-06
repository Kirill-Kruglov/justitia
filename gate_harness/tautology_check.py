"""Tautology-of-construction pre-check (recovered spec §1.6, fixes finding #5).

The B1.1 world sets ``bias = -group_center`` exactly, so the observed ``y``
carries almost no information about the latent ``z`` *before any learner runs*.
"no-aux fails / with-aux succeeds" is then partly guaranteed by construction, not
demonstrated. This module makes that measurable and un-hideable.

Two obligations, both automatic (pipeline steps, not opt-in):

1. ``tautology_precheck`` computes ``information_ratio = var(y)/var(z)`` on the
   freshly generated world, BEFORE any learner. ``information_ratio_min`` is a
   MANDATORY prereg field — if absent, this raises (never silent). If the ratio
   is below it, the returned report carries
   ``construction_may_be_tautological = True``. Only this module sets that field;
   the runner must copy it verbatim into the decision JSON and experiment code
   may not override it.

2. ``run_generic_baselines`` runs >= 2 strong unsupervised baselines
   (k-means at the known group count; BIC-selected 1D GMM) against the no-aux
   threshold, and emits the verbatim honesty string with N substituted.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

VERBATIM_HONESTY_TEMPLATE = (
    "no-aux failure demonstrated against {N} generic baselines; "
    "does not by construction prove non-tautological information loss"
)


class TautologyError(RuntimeError):
    pass


def _abs_corr(a: Sequence[float], b: Sequence[float]) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.std() == 0 or b.std() == 0 or len(a) < 2:
        return 0.0
    return float(abs(np.corrcoef(a, b)[0, 1]))


def information_ratio(y: Sequence[float], z: Sequence[float]) -> float:
    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)
    var_z = float(z.var())
    if var_z == 0.0:
        raise TautologyError("var(z_obj) == 0; information_ratio undefined (fail closed)")
    return float(y.var()) / var_z


def tautology_precheck(
    y: Sequence[float],
    z: Sequence[float],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Compute information_ratio and the immutable tautology flag. Fail closed."""
    if "information_ratio_min" not in thresholds:
        raise TautologyError(
            "information_ratio_min is a mandatory prereg field with no default; "
            "tautology_check refuses to run without it (fail closed)"
        )
    ratio = information_ratio(y, z)
    threshold = float(thresholds["information_ratio_min"])
    return {
        "information_ratio": ratio,
        "information_ratio_min": threshold,
        "computed_before_learner": True,
        # set ONLY here; runner copies verbatim, experiment code may not override
        "construction_may_be_tautological": ratio < threshold,
    }


# --------------------------------------------------------------------------- #
# strong unsupervised baselines
# --------------------------------------------------------------------------- #
def _kmeans_1d(x: np.ndarray, k: int, iters: int = 200, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centers = np.sort(rng.choice(x, size=k, replace=False))
    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        labels = np.argmin(np.abs(x[:, None] - centers[None, :]), axis=1)
        new = np.array([x[labels == c].mean() if np.any(labels == c) else centers[c] for c in range(k)])
        if np.allclose(new, centers):
            break
        centers = new
    order = np.argsort(centers)
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[c] for c in labels])


def _gmm_1d_bic(x: np.ndarray, k: int, iters: int = 100) -> tuple[float, np.ndarray]:
    n = len(x)
    q = np.quantile(x, np.linspace(0.1, 0.9, k))
    mu = q.copy()
    var = np.full(k, max(x.var(), 1e-6))
    w = np.full(k, 1.0 / k)
    ll = -np.inf
    resp = np.full((n, k), 1.0 / k)
    for _ in range(iters):
        # E-step
        comp = w[None, :] * np.exp(-0.5 * (x[:, None] - mu[None, :]) ** 2 / var[None, :]) / np.sqrt(2 * np.pi * var[None, :])
        total = comp.sum(axis=1, keepdims=True)
        total[total == 0] = 1e-300
        resp = comp / total
        new_ll = float(np.log(comp.sum(axis=1) + 1e-300).sum())
        # M-step
        nk = resp.sum(axis=0) + 1e-9
        w = nk / n
        mu = (resp * x[:, None]).sum(axis=0) / nk
        var = (resp * (x[:, None] - mu[None, :]) ** 2).sum(axis=0) / nk
        var = np.maximum(var, 1e-6)
        if abs(new_ll - ll) < 1e-6:
            ll = new_ll
            break
        ll = new_ll
    p = 3 * k - 1  # means + vars + (weights-1)
    bic = -2 * ll + p * math.log(n)
    return bic, resp


def _gmm_1d_best(x: np.ndarray, k_max: int = 6) -> np.ndarray:
    best_bic, best_labels = np.inf, np.zeros(len(x), dtype=int)
    for k in range(1, k_max + 1):
        try:
            bic, resp = _gmm_1d_bic(x, k)
        except Exception:  # noqa: BLE001 - a degenerate k just loses the tournament
            continue
        if bic < best_bic:
            centers = (resp * x[:, None]).sum(axis=0) / (resp.sum(axis=0) + 1e-9)
            hard = resp.argmax(axis=1)
            order = np.argsort(centers)
            remap = {old: new for new, old in enumerate(order)}
            best_bic, best_labels = bic, np.array([remap[c] for c in hard])
    return best_labels


def run_generic_baselines(
    y: Sequence[float],
    z: Sequence[float],
    n_groups: int,
    no_aux_abs_corr_max: float,
) -> dict[str, Any]:
    """Run the two mandatory strong unsupervised baselines; emit verbatim string."""
    x = np.asarray(y, dtype=float)
    zz = np.asarray(z, dtype=float)
    kmeans_corr = _abs_corr(_kmeans_1d(x, n_groups), zz)
    gmm_corr = _abs_corr(_gmm_1d_best(x), zz)
    baselines = {
        "kmeans_known_group_count": {"abs_corr": kmeans_corr, "beats_no_aux_threshold": kmeans_corr > no_aux_abs_corr_max},
        "gmm_bic_selected": {"abs_corr": gmm_corr, "beats_no_aux_threshold": gmm_corr > no_aux_abs_corr_max},
    }
    n = len(baselines)
    return {
        "baselines": baselines,
        "n_baselines": n,
        "no_aux_abs_corr_max": no_aux_abs_corr_max,
        "any_strong_baseline_recovers": any(b["beats_no_aux_threshold"] for b in baselines.values()),
        "honesty_statement": VERBATIM_HONESTY_TEMPLATE.format(N=n),
    }

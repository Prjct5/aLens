"""Fellegi-Sunter tests, including the handbook's worked example (section 6.5)."""

import numpy as np
import pytest

from autolens.linkage.fs import fs_em, match_weight, posterior_from_weight


def test_worked_example_from_handbook():
    m = np.array([0.95, 0.70, 0.50])
    u = np.array([0.25, 0.05, 0.001])
    # Pair A: agrees year + mileage, disagrees photo -> 4.74 bits
    # Pair B: agrees all three -> 14.71 bits
    G = np.array([[1, 1, 0], [1, 1, 1]], dtype=np.int8)
    w = match_weight(G, m, u)
    assert w[0] == pytest.approx(4.74, abs=0.02)
    assert w[1] == pytest.approx(14.71, abs=0.02)
    # Posterior with prior 0.001: ~2.6% and ~96%
    p = posterior_from_weight(w, 0.001)
    assert p[0] == pytest.approx(0.026, abs=0.005)
    assert p[1] == pytest.approx(0.964, abs=0.01)


def test_em_converges_on_synthetic_data():
    rng = np.random.default_rng(7)
    n, K = 4000, 4
    true_m = np.array([0.9, 0.8, 0.7, 0.95])
    true_u = np.array([0.1, 0.2, 0.3, 0.05])
    true_labels = rng.random(n) < 0.2
    G = np.empty((n, K), dtype=np.int8)
    for k in range(K):
        probs = np.where(true_labels, true_m[k], true_u[k])
        G[:, k] = (rng.random(n) < probs).astype(np.int8)
    m, u, p, g = fs_em(G, p0=0.2, tol=1e-7, prior_bounds=(1e-5, 0.5))
    assert np.all(m > u), "match probabilities must exceed non-match probabilities"
    assert abs(p - 0.2) < 0.08
    assert np.mean((g > 0.5) == true_labels) > 0.85


def test_missing_values_are_not_disagreements():
    G = np.array([[1, -1, 0], [1, 1, 1]], dtype=np.int8)
    m, u, p, g = fs_em(G)
    w = match_weight(G, m, u)
    assert np.isfinite(w).all(), "missing fields must contribute zero, not NaN"
    # A pair with a missing field cannot have a larger |weight| than one with
    # the same agreements observed on every field.
    G_full = np.array([[1, 0, 0]], dtype=np.int8)
    assert abs(w[0]) <= abs(match_weight(G_full, m, u)[0]) + 1e-9

"""Fellegi-Sunter with EM - handbook 6.5, 6.6, Listing 8.3.

Handles three-level comparison vectors: -1 = missing contributes no evidence
and is excluded from the m/u M-step estimates (section 8.7.2).
"""

from __future__ import annotations

import numpy as np


def fs_em(
    G: np.ndarray,
    p0: float = 0.01,
    m0: float = 0.9,
    u0: float = 0.1,
    tol: float = 1e-6,
    max_iter: int = 200,
    prior_bounds: tuple[float, float] = (1e-5, 0.05),
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """Estimate m, u, prior p and posterior g for candidate pairs."""
    G = np.asarray(G)
    n, K = G.shape
    observed = G >= 0
    G0 = np.where(observed, G, 0).astype(float)
    m = np.full(K, m0)
    u = np.full(K, u0)
    p = p0
    eps = 1e-6
    for _ in range(max_iter):
        # E-step in the log domain for stability (Listing 8.3).
        log_m = np.where(observed, G0 * np.log(m) + (1 - G0) * np.log(1 - m), 0).sum(1) + np.log(p)
        log_u = np.where(observed, G0 * np.log(u) + (1 - G0) * np.log(1 - u), 0).sum(1) + np.log(
            1 - p
        )
        g = 1.0 / (1.0 + np.exp(np.clip(log_u - log_m, -700, 700)))

        # M-step: count only observed comparisons (missing != disagreement).
        obs_g = observed * g[:, None]
        obs_ng = observed * (1 - g)[:, None]
        m_num = (obs_g * G0).sum(0)
        m_den = obs_g.sum(0)
        u_num = (obs_ng * G0).sum(0)
        u_den = obs_ng.sum(0)
        m_new = np.clip(np.divide(m_num, m_den, out=np.full(K, m0), where=m_den > 0), eps, 1 - eps)
        u_new = np.clip(np.divide(u_num, u_den, out=np.full(K, u0), where=u_den > 0), eps, 1 - eps)
        # Practical guard from 6.6: true matches are rare among candidate
        # pairs (~0.1%). Cap the EM prior so it cannot drift to an implausible
        # local optimum where a large share of pairs are labelled "match".
        p_new = float(np.clip(g.mean(), prior_bounds[0], prior_bounds[1]))
        done = max(abs(m_new - m).max(), abs(u_new - u).max(), abs(p_new - p)) < tol
        m, u, p = m_new, u_new, p_new
        if done:
            break
    return m, u, p, g


def match_weight(G: np.ndarray, m: np.ndarray, u: np.ndarray) -> np.ndarray:
    """w_j = sum_k [gamma*log2(m/u) + (1-gamma)*log2((1-m)/(1-u))] in bits."""
    G = np.asarray(G)
    observed = G >= 0
    G0 = np.where(observed, G, 0).astype(float)
    terms = G0 * np.log2(m / u) + (1 - G0) * np.log2((1 - m) / (1 - u))
    return np.where(observed, terms, 0).sum(1)


def posterior_from_weight(w: np.ndarray, prior: float) -> np.ndarray:
    """posterior odds = prior * 2^w (worked example, section 6.5)."""
    odds = prior * np.power(2.0, np.asarray(w))
    return odds / (1 + odds)

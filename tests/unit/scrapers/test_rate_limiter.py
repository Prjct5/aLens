"""Politeness config tests (R5, 6.1)."""

import pytest

from autolens.scrapers.rate_limiter import PolitePolicy, RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_interval_cannot_be_lowered():
    with pytest.raises(ValueError):
        RateLimiter(0.5)


def test_limiter_uses_interval(monkeypatch):
    clock = FakeClock()
    slept = []
    monkeypatch.setattr("autolens.scrapers.rate_limiter.time.sleep", lambda s: slept.append(s))
    limiter = RateLimiter(1.0, clock=clock)
    limiter.wait()
    clock.t = 0.4
    limiter.wait()
    assert slept and slept[0] == pytest.approx(0.6, abs=1e-6)


def test_policy_defaults():
    p = PolitePolicy()
    assert p.min_interval_s >= 1.0
    assert p.concurrency <= 2

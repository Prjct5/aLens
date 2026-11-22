"""Politeness: rate limit + robots.txt + identifiable User-Agent (R5, 6.1)."""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass


@dataclass
class PolitePolicy:
    min_interval_s: float = 1.0
    concurrency: int = 2
    user_agent: str = "AutoLens-Egypt/0.1 (academic research)"
    off_peak_only: bool = True

    def check_robots(self, base_url: str, path: str = "/") -> bool:
        """Return True if our user-agent may fetch `path` (6.1)."""
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base_url.rstrip("/") + "/robots.txt")
        try:
            rp.read()
        except Exception:
            # Offline / unavailable: be conservative and report as not allowed.
            return False
        return rp.can_fetch(self.user_agent.split()[0], path)


class RateLimiter:
    """Simple monotonic-clock limiter, testable with a fake clock (11.4)."""

    def __init__(self, min_interval_s: float, clock=time.monotonic):
        if min_interval_s < 1.0:
            raise ValueError("politeness default is >= 1 request/second; cannot lower")
        self.interval = min_interval_s
        self._clock = clock
        self._last = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.interval - (now - self._last)
            if remaining > 0:
                time.sleep(remaining)
        self._last = self._clock()

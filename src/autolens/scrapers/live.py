"""Compliant *live* fetcher scaffold (handbook R1/R4/R5, 6.1, 8.1-8.3).

This module is the production hand-off point. It is deliberately not wired into
the default pipeline: the supplied archives are the only data we are permitted
to use until source owners grant permission and the team verifies robots/terms.
To activate, a team member must:
  1. approve docs/sources/<source>.md with live robots/terms evidence,
  2. inject an approved parser (``parse_fn``) and index URL builder,
  3. set AUTOLENS_LIVE_ENABLED=1 and run the nightly workflow.

The fetcher itself is strict: it refuses to start without a passing robots.txt
check, sends an identifiable User-Agent, obeys >=1s intervals, off-peak windows,
and STOPS on 403/429/CAPTCHA (never evades - runbook "Restart a failed source").
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from autolens.scrapers.rate_limiter import PolitePolicy, RateLimiter


class BlockedError(RuntimeError):
    """Raised on 403/429/CAPTCHA - the caller MUST stop, not retry aggressively."""


class RobotsDenied(RuntimeError):
    """robots.txt disallows this path (or could not be verified)."""


@dataclass
class FetchResult:
    url: str
    payload: bytes
    status: int
    fetched_at: str


class LiveSourceScraper:
    def __init__(
        self, base_url: str, policy: PolitePolicy | None = None, limiter: RateLimiter | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.policy = policy or PolitePolicy()
        self.limiter = limiter or RateLimiter(self.policy.min_interval_s)
        self._client = httpx.Client(
            headers={"User-Agent": self.policy.user_agent},
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
        )

    def assert_allowed(self, path: str = "/") -> None:
        if not self.policy.check_robots(self.base_url, path):
            raise RobotsDenied(f"robots.txt denies or unverifiable: {self.base_url}{path}")

    def _off_peak(self, now: datetime | None = None) -> bool:
        if not self.policy.off_peak_only:
            return True
        moment = now or datetime.now(UTC)
        return 1 <= moment.astimezone(ZoneInfo("Africa/Cairo")).hour < 6

    def fetch(self, path: str, *, enforce_peak: bool = True) -> FetchResult:
        self.assert_allowed(path)
        if enforce_peak and not self._off_peak():
            raise RuntimeError("outside off-peak window; postponed without making a request")
        self.limiter.wait()
        response = self._client.get(self.base_url + path)
        if response.status_code in {403, 429} or _looks_like_captcha(response.text):
            raise BlockedError(
                f"{response.status_code} from {path}; stop, lower rate, back off, notify team"
            )
        response.raise_for_status()
        return FetchResult(
            self.base_url + path,
            response.content,
            response.status_code,
            datetime.now(UTC).isoformat(),
        )

    def discover(self, index_paths: Iterator[str]) -> Iterator[FetchResult]:
        """Yield index pages politely; a BlockedError aborts the whole sweep."""
        for path in index_paths:
            yield self.fetch(path)

    def close(self) -> None:
        self._client.close()


def _looks_like_captcha(text: str) -> bool:
    low = text.lower()
    return "captcha" in low or "cf-challenge" in low or "are you a robot" in low

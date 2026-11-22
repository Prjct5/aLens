"""Configuration is read only from environment variables (handbook 14.2)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class M1Settings:
    root: Path
    data_dir: Path
    output_dir: Path
    raw_dir: Path
    quarantine_dir: Path
    db_path: Path
    run_date: str
    min_interval_s: float
    concurrency: int
    user_agent: str
    log_level: str
    reference_dir: Path | None = None
    photo_match_statuses: tuple[str, ...] = ("fetched", "promoted")
    max_candidate_pairs: int = 2_000_000
    reparse_sample: int = 200

    @classmethod
    def from_env(cls) -> M1Settings:
        root = Path(_env("PROJECT_ROOT", ".")).resolve()
        return cls(
            root=root,
            data_dir=root / _env("DATA_DIR", "data"),
            output_dir=root / _env("OUTPUT_DIR", "outputs"),
            raw_dir=root / _env("RAW_DIR", "raw"),
            quarantine_dir=root / _env("QUARANTINE_DIR", "quarantine"),
            db_path=root / _env("DB_PATH", "outputs/autolens.db"),
            run_date=_env("RUN_DATE", "2026-01-15"),
            min_interval_s=float(_env("SCRAPER_MIN_INTERVAL_S", "1.0")),
            concurrency=int(_env("SCRAPER_CONCURRENCY", "2")),
            user_agent=_env(
                "SCRAPER_USER_AGENT",
                "AutoLens-Egypt/0.1 (academic research; contact: TEAM_EMAIL)",
            ),
            log_level=_env("LOG_LEVEL", "INFO"),
            reference_dir=root / _env("REFERENCE_DIR", "data_reference"),
            photo_match_statuses=tuple(
                x.strip()
                for x in _env("PHOTO_MATCH_STATUSES", "fetched,promoted").split(",")
                if x.strip()
            ),
            max_candidate_pairs=int(_env("MAX_CANDIDATE_PAIRS", "2000000")),
            reparse_sample=int(_env("REPARSE_SAMPLE", "200")),
        )

    @property
    def reference_path(self) -> Path:
        return self.reference_dir or (self.root / "data_reference")

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.output_dir, self.raw_dir, self.quarantine_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

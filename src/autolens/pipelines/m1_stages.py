from __future__ import annotations

from dataclasses import replace
from datetime import date

from autolens.common.stage import RunContext, Stage, StageResult
from autolens.linkage.run import run_linkage
from autolens.scrapers.images import run_fetch_images
from autolens.scrapers.run import run_normalize, run_scrape
from autolens.scrapers.settings import M1Settings


def _m1_ctx(ctx: RunContext) -> RunContext:
    """Give M1's stages their file-based settings while sharing db, store and logger."""
    return replace(ctx, settings=M1Settings.from_env())  # type: ignore[type-var]


def scrape(run_date: date, ctx: RunContext) -> StageResult:
    return run_scrape(run_date, _m1_ctx(ctx))


def normalize(run_date: date, ctx: RunContext) -> StageResult:
    return run_normalize(run_date, _m1_ctx(ctx))


def fetch_images(run_date: date, ctx: RunContext) -> StageResult:
    return run_fetch_images(run_date, _m1_ctx(ctx))


def linkage(run_date: date, ctx: RunContext) -> StageResult:
    return run_linkage(run_date, _m1_ctx(ctx))


M1_STAGES: dict[str, Stage] = {
    "scrape": scrape,
    "normalize": normalize,
    "fetch_images": fetch_images,
    "linkage": linkage,
}

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import httpx

from autolens.common.config import Settings, get_settings
from autolens.common.db import Database
from autolens.common.logging import configure_logging, get_logger
from autolens.common.store import QUARANTINE, ObjectStore

TITLE_PREFIX = "[alert] "
LABEL = "pipeline-failure"


@dataclass(frozen=True)
class Alert:
    key: str
    body: str
    owner: str

    @property
    def title(self) -> str:
        return f"{TITLE_PREFIX}{self.key}"


def check_pipeline_runs(db: Database, today: date) -> list[Alert]:
    rows = db.fetch_all(
        "SELECT DISTINCT stage FROM ops.pipeline_run WHERE run_date = %s AND status = 'failed'",
        (today,),
    )
    return [
        Alert(
            f"pipeline stage failed: {r['stage']}", f"Stage {r['stage']} failed on {today}.", "m5"
        )
        for r in rows
    ]


def check_quarantine(store: ObjectStore, max_days: int) -> list[Alert]:
    n = store.count_older_than(QUARANTINE, max_days)
    if n == 0:
        return []
    return [
        Alert(
            "privacy: quarantine objects past retention warning",
            f"{n} unblurred objects in quarantine are older than {max_days} days.",
            "m3",
        )
    ]


def check_lifecycle(store: ObjectStore) -> list[Alert]:
    rules = store.lifecycle_rules(QUARANTINE)
    active = [r for r in rules if r.get("Status") == "Enabled" and "Expiration" in r]
    if active:
        return []
    return [
        Alert(
            "privacy: quarantine lifecycle rule missing",
            "No enabled expiration rule on the quarantine bucket.",
            "m5",
        )
    ]


def collect_alerts(settings: Settings, today: date) -> list[Alert]:
    alerts: list[Alert] = []
    db = Database.from_settings(settings)
    try:
        if db.table_exists("ops.pipeline_run"):
            alerts += check_pipeline_runs(db, today)
    finally:
        db.close()
    store = ObjectStore(settings)
    alerts += check_quarantine(store, settings.quarantine_alert_days)
    alerts += check_lifecycle(store)
    return alerts


def sync_issues(client: httpx.Client, repo: str, alerts: list[Alert]) -> dict[str, list[str]]:
    base = f"/repos/{repo}/issues"
    open_issues: list[dict[str, Any]] = (
        client.get(base, params={"state": "open", "labels": LABEL, "per_page": 100})
        .raise_for_status()
        .json()
    )
    by_title = {i["title"]: i for i in open_issues if i["title"].startswith(TITLE_PREFIX)}
    summary: dict[str, list[str]] = {"opened": [], "commented": [], "closed": []}
    current = {a.title for a in alerts}
    for alert in alerts:
        if alert.title in by_title:
            number = by_title[alert.title]["number"]
            client.post(f"{base}/{number}/comments", json={"body": alert.body}).raise_for_status()
            summary["commented"].append(alert.title)
        else:
            client.post(
                base,
                json={"title": alert.title, "body": alert.body, "labels": [LABEL, alert.owner]},
            ).raise_for_status()
            summary["opened"].append(alert.title)
    for title, issue in by_title.items():
        if title not in current:
            number = issue["number"]
            client.post(
                f"{base}/{number}/comments", json={"body": "Alert cleared."}
            ).raise_for_status()
            client.patch(f"{base}/{number}", json={"state": "closed"}).raise_for_status()
            summary["closed"].append(title)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly health evaluation")
    parser.add_argument("--open-issues", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("health")
    from autolens.common.time import today_cairo

    alerts = collect_alerts(settings, today_cairo())
    print(json.dumps([asdict(a) for a in alerts], indent=2))
    if args.open_issues:
        if not settings.gh_token:
            print("GH_TOKEN not set", file=sys.stderr)
            return 2
        with httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {settings.gh_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        ) as client:
            summary = sync_issues(client, settings.github_repository, alerts)
        log.info("issues synced", **summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

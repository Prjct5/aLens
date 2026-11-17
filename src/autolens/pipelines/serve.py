from __future__ import annotations

from prefect import serve
from prefect.schedules import Cron

from autolens.pipelines.daily import daily


def main() -> None:
    deployment = daily.to_deployment(
        name="daily-0200-cairo",
        schedule=Cron("0 2 * * *", timezone="Africa/Cairo"),
    )
    serve(deployment)


if __name__ == "__main__":
    main()

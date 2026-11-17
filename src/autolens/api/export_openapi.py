from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autolens.api.main import create_app
from autolens.common.config import Settings
from autolens.common.logging import get_logger
from autolens.common.stage import RunContext

OPENAPI_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


def generate() -> str:
    settings = Settings(_env_file=None, environment="dev")
    ctx = RunContext(settings=settings, log=get_logger("openapi"))
    return json.dumps(create_app(ctx).openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or check contracts/openapi.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = generate()
    if args.check:
        if not OPENAPI_PATH.exists() or OPENAPI_PATH.read_text(encoding="utf-8") != content:
            print("drift: contracts/openapi.json", file=sys.stderr)
            return 1
        return 0
    OPENAPI_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

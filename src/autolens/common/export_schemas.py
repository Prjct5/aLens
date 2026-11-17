from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autolens.common.schemas import CONTRACT_MODELS, CONTRACT_VERSION

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"


def render() -> dict[str, str]:
    files = {
        f"{name}.schema.json": json.dumps(model.model_json_schema(), indent=2, sort_keys=True)
        + "\n"
        for name, model in sorted(CONTRACT_MODELS.items())
    }
    files["CONTRACT_VERSION"] = f"{CONTRACT_VERSION}\n"
    return files


def check(directory: Path = CONTRACTS_DIR) -> list[str]:
    expected = render()
    problems: list[str] = []
    for fname, content in expected.items():
        path = directory / fname
        if not path.exists():
            problems.append(f"missing: {fname}")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"drift: {fname}")
    for path in directory.glob("*.schema.json"):
        if path.name not in expected:
            problems.append(f"stale: {path.name}")
    return problems


def write(directory: Path = CONTRACTS_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    expected = render()
    for path in directory.glob("*.schema.json"):
        if path.name not in expected:
            path.unlink()
    for fname, content in expected.items():
        (directory / fname).write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Pydantic contracts to contracts/")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args()
    if args.check:
        problems = check()
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

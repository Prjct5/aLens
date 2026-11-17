from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from autolens.common.time import utcnow
from autolens.mlops.evaluators import EVALUATORS

GATES_PATH = Path(__file__).with_name("gates.yaml")


def load_policy(model: str, path: Path = GATES_PATH) -> dict[str, dict[str, Any]]:
    policies = yaml.safe_load(path.read_text(encoding="utf-8"))["models"]
    if model not in policies:
        raise KeyError(f"no gate policy for model '{model}' in {path.name}")
    return dict(policies[model])


def _check_metric(
    name: str, rule: dict[str, Any], cand: float | None, champ: float | None
) -> dict[str, Any]:
    higher = rule["direction"] == "higher_is_better"
    result: dict[str, Any] = {"metric": name, "candidate": cand, "champion": champ, "passed": True}
    reasons: list[str] = []
    if cand is None:
        result.update(passed=False, reason="candidate metric missing")
        return result
    if "floor" in rule and cand < rule["floor"]:
        reasons.append(f"below floor {rule['floor']}")
    if "max_absolute" in rule and cand > rule["max_absolute"]:
        reasons.append(f"above limit {rule['max_absolute']}")
    if champ is not None:
        if "max_relative_regression" in rule:
            tol = rule["max_relative_regression"]
            if higher and cand < champ * (1 - tol):
                reasons.append(f"regressed more than {tol:.0%} vs champion")
            if not higher and cand > champ * (1 + tol):
                reasons.append(f"regressed more than {tol:.0%} vs champion")
        if "max_absolute_regression" in rule:
            tol = rule["max_absolute_regression"]
            if higher and cand < champ - tol:
                reasons.append(f"regressed more than {tol} vs champion")
            if not higher and cand > champ + tol:
                reasons.append(f"regressed more than {tol} vs champion")
    if reasons:
        result.update(passed=False, reason="; ".join(reasons))
    return result


def evaluate_gate(
    model: str,
    version: str,
    policy: dict[str, dict[str, Any]],
    candidate: dict[str, float],
    champion: dict[str, float] | None,
) -> dict[str, Any]:
    checks = [
        _check_metric(name, rule, candidate.get(name), (champion or {}).get(name))
        for name, rule in policy.items()
    ]
    return {
        "model": model,
        "candidate_version": version,
        "evaluated_at": utcnow().isoformat(),
        "has_champion": champion is not None,
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }


def _champion_version(model: str) -> str | None:
    from mlflow.tracking import MlflowClient

    try:
        return str(MlflowClient().get_model_version_by_alias(model, "champion").version)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Model promotion gate")
    parser.add_argument("--model", required=True)
    parser.add_argument("--candidate", required=True, help="candidate version")
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate-metrics", help="JSON file instead of running the evaluator")
    parser.add_argument("--champion-metrics", help="JSON file instead of running the evaluator")
    args = parser.parse_args()

    policy = load_policy(args.model)
    if args.candidate_metrics:
        candidate = json.loads(Path(args.candidate_metrics).read_text(encoding="utf-8"))
        champion = (
            json.loads(Path(args.champion_metrics).read_text(encoding="utf-8"))
            if args.champion_metrics
            else None
        )
    else:
        evaluator = EVALUATORS.get(args.model)
        if evaluator is None:
            print(f"no evaluator registered for '{args.model}'", file=sys.stderr)
            return 2
        candidate = evaluator(args.model, args.candidate)
        champ_version = _champion_version(args.model)
        champion = evaluator(args.model, champ_version) if champ_version else None

    report = evaluate_gate(args.model, args.candidate, policy, candidate, champion)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

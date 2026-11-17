from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a model version to champion")
    parser.add_argument("--model", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--override-approved-by", help="owner and M5, comma separated")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if not report.get("passed") and not args.override_approved_by:
        print("gate failed: champion alias not moved", file=sys.stderr)
        return 1

    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    version = client.get_model_version(args.model, args.version)
    if version.run_id:
        client.log_artifact(version.run_id, args.report, artifact_path="gate")
    client.set_registered_model_alias(args.model, "champion", args.version)
    if args.override_approved_by:
        client.set_model_version_tag(
            args.model, args.version, "gate_override_by", args.override_approved_by
        )
    print(f"{args.model} v{args.version} is now champion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

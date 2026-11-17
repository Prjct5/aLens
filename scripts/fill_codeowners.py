from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".github" / "CODEOWNERS.template"
TARGET = ROOT / ".github" / "CODEOWNERS"


def render(usernames: dict[str, str]) -> str:
    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        path, *owners = line.split()
        resolved: list[str] = []
        for owner in owners:
            code = owner.removeprefix("@").removesuffix("_USERNAME")
            name = "@" + usernames[code].removeprefix("@")
            if name not in resolved:
                resolved.append(name)
        lines.append(f"{path} {' '.join(resolved)}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate .github/CODEOWNERS from the template")
    for code in ("M1", "M2", "M3", "M4", "M5"):
        parser.add_argument(f"--{code.lower()}", required=True, help=f"GitHub username of {code}")
    args = parser.parse_args()
    usernames = {c: getattr(args, c.lower()) for c in ("M1", "M2", "M3", "M4", "M5")}
    TARGET.write_text(render(usernames), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()

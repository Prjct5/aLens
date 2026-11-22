from __future__ import annotations

import re
from pathlib import Path

NON_COLUMNS = {"primary", "unique", "constraint", "foreign", "check", "exclude", "like"}
_TABLE = re.compile(
    r"CREATE TABLE(?: IF NOT EXISTS)?\s+([\w.]+)\s*\((.*?)\n\)\s*;", re.DOTALL | re.IGNORECASE
)


def _strip_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


def _split_top_level(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    in_quote = False
    for ch in body:
        if ch == "'":
            in_quote = not in_quote
        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
        current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def ddl_columns(sql_text: str) -> dict[str, list[str]]:
    """Column names per table; handles several columns per line, comments and nested parens."""
    tables: dict[str, list[str]] = {}
    for name, body in _TABLE.findall(_strip_comments(sql_text)):
        columns = []
        for item in _split_top_level(body):
            token = item.split()[0].strip('"').lower()
            if token not in NON_COLUMNS:
                columns.append(token)
        tables[name.lower()] = columns
    return tables


def ddl_columns_from_dir(directory: Path) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.sql")):
        tables.update(ddl_columns(path.read_text(encoding="utf-8")))
    return tables

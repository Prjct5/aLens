from __future__ import annotations

from pathlib import Path

import pytest

from autolens.warehouse.migrate import MigrationError, migration_files


def test_both_naming_styles_are_ordered_by_number(tmp_path: Path) -> None:
    for name in (
        "110_core_links.sql",
        "V201__dims.sql",
        "000_schemas.sql",
        "V202__facts.sql",
        "020_x.sql",
    ):
        (tmp_path / name).write_text("SELECT 1;")
    assert [p.name for p in migration_files(tmp_path)] == [
        "000_schemas.sql",
        "020_x.sql",
        "110_core_links.sql",
        "V201__dims.sql",
        "V202__facts.sql",
    ]


def test_unnumbered_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "dims.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError):
        migration_files(tmp_path)

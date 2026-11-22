from __future__ import annotations

from datetime import date
from types import ModuleType

import pytest

from autolens.common.config import Settings
from autolens.common.stage import make_context
from autolens.pipelines.entrypoints import OPTIONAL_STAGES, load_optional
from autolens.pipelines.gates import dq_gate
from autolens.pipelines.stages import STAGE_NAMES


def _module(name: str, **attrs: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _missing(name: str):
    def importer(module: str) -> ModuleType:
        raise ModuleNotFoundError(f"No module named {module!r}", name=name)

    return importer


def test_every_optional_stage_name_is_a_real_stage() -> None:
    assert set(OPTIONAL_STAGES) <= set(STAGE_NAMES)


def test_missing_modules_are_skipped_and_present_ones_registered() -> None:
    def fn(run_date, ctx):
        return None

    def importer(name: str) -> ModuleType:
        if name == "autolens.warehouse.macro":
            return _module(name, run_macro=fn)
        raise ModuleNotFoundError(name=name)

    found = load_optional(OPTIONAL_STAGES, importer)
    assert found == {"macro": fn}


def test_missing_function_in_existing_module_is_an_error() -> None:
    with pytest.raises(ImportError, match="run_macro"):
        load_optional({"macro": ("m", "run_macro")}, lambda name: _module(name))


def test_import_error_inside_a_member_module_is_not_hidden() -> None:
    def importer(name: str) -> ModuleType:
        raise ModuleNotFoundError("No module named 'torch'", name="torch")

    with pytest.raises(ModuleNotFoundError):
        load_optional({"macro": ("autolens.warehouse.macro", "run_macro")}, importer)


def _ctx():
    return make_context(Settings(_env_file=None), connect=False)


def test_gate_defaults_to_open_when_m2_has_not_written_dq_yet() -> None:
    assert dq_gate(date(2026, 1, 15), _ctx(), importer=_missing("autolens.warehouse.dq")) is True


def test_gate_supports_both_signatures_and_can_block() -> None:
    one = _module("dq", dq_gate=lambda run_date: False)
    two = _module("dq", dq_gate=lambda run_date, ctx: True)
    assert dq_gate(date(2026, 1, 15), _ctx(), importer=lambda n: one) is False
    assert dq_gate(date(2026, 1, 15), _ctx(), importer=lambda n: two) is True

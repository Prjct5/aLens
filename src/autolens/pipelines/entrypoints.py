from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from types import ModuleType

from autolens.common.stage import Stage
from autolens.pipelines.m1_stages import M1_STAGES

# stage name -> (module, function). Registered automatically as soon as the module exists,
# so a member only has to create the module; a missing function is an error, not a skip.
OPTIONAL_STAGES: dict[str, tuple[str, str]] = {
    "macro": ("autolens.warehouse.macro", "run_macro"),
    "load_core": ("autolens.warehouse.load", "run_load_core"),
    "dq": ("autolens.warehouse.dq", "run_dq"),
    "build_marts": ("autolens.features.build", "run_build_marts"),
    "analytics": ("autolens.analytics.run", "run_analytics"),
    "privacy_blur": ("autolens.vision.run", "run_privacy"),
    "score_images": ("autolens.vision.run", "run_score_images"),
    "text_features": ("autolens.nlp.run", "run_text_features"),
    "score_prices": ("autolens.pricing.run", "run_score_prices"),
    "fraud": ("autolens.pricing.run", "run_fraud"),
    "calibration_update": ("autolens.pricing.run", "run_calibration_update"),
}


def load_optional(
    optional: Mapping[str, tuple[str, str]],
    importer: Callable[[str], ModuleType] = import_module,
) -> dict[str, Stage]:
    found: dict[str, Stage] = {}
    for stage, (module_name, function) in optional.items():
        try:
            module = importer(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            continue
        try:
            found[stage] = getattr(module, function)
        except AttributeError as exc:
            raise ImportError(
                f"{module_name} exists but has no function {function}() for stage '{stage}'"
            ) from exc
    return found


IMPLEMENTATIONS: dict[str, Stage] = {}

IMPLEMENTATIONS.update(M1_STAGES)
IMPLEMENTATIONS.update(load_optional(OPTIONAL_STAGES))

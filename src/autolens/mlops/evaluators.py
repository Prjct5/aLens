from __future__ import annotations

from collections.abc import Callable

Evaluator = Callable[[str, str], dict[str, float]]

EVALUATORS: dict[str, Evaluator] = {}

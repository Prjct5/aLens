"""Canonical make/model dictionary and alias mining (handbook 8.5, 6.4).

The handbook builds the vocabulary from official new-car price lists. None were
supplied, so the seed is mined from the observed listings themselves (the most
frequent spelling per make+model becomes canonical). Every accepted alias is
written to git-tracked CSVs, exactly as the handbook requires.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from autolens.common.text import normalize_arabic, similarity

FUZZY_THRESHOLD = 0.85  # 8.5 step 3

# Makes whose canonical name contains a space. Splitting on the first space
# would wrongly turn "Land Rover" into make="Land", model="Rover Range Rover".
MULTIWORD_MAKES = (
    "Alfa Romeo",
    "Aston Martin",
    "Great Wall",
    "Land Rover",
    "Mercedes Benz",
    "Rolls Royce",
)


def _split_make_model(make_raw: str, model_raw: str) -> tuple[str, str]:
    """Prefer the source's own make/model fields; only split as a fallback.

    The supplied archives give make and model in separate columns. Using them
    directly is the only reliable way to preserve multi-word makes. When the
    make column is empty we split the combined label, but never inside a known
    multi-word make.
    """
    make, model = (make_raw or "").strip(), (model_raw or "").strip()
    if make:
        return make, model
    label = f"{make} {model}".strip()
    for candidate in sorted(MULTIWORD_MAKES, key=len, reverse=True):
        if label.lower().startswith(candidate.lower()):
            return candidate, label[len(candidate) :].strip()
    parts = label.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


@dataclass
class ModelDictionary:
    models: dict[int, dict] = field(default_factory=dict)  # model_id -> row
    aliases: dict[str, tuple[int, float]] = field(default_factory=dict)  # norm key -> (id, conf)
    _by_id: dict[str, int] = field(default_factory=dict)  # "make|model" -> id

    @staticmethod
    def key(make_raw: str | None, model_raw: str | None) -> str:
        return normalize_arabic(f"{make_raw or ''} {model_raw or ''}").strip()

    def fit(self, listings) -> ModelDictionary:
        """Mine aliases from observed make_raw/model_raw strings."""
        counts: Counter[str] = Counter()
        display: dict[str, Counter[tuple[str, str]]] = {}
        for lst in listings:
            make_raw = getattr(lst, "make_raw", None) or ""
            model_raw = getattr(lst, "model_raw", None) or ""
            k = self.key(make_raw, model_raw)
            if not k:
                continue
            counts[k] += 1
            display.setdefault(k, Counter())[(make_raw, model_raw)] += 1

        # Canonical entries: most frequent normalized make+model strings first.
        model_id = 0
        for norm_key, n in counts.most_common():
            make_raw, model_raw = display[norm_key].most_common(1)[0][0]
            make, model = _split_make_model(make_raw, model_raw)
            model_id += 1
            self.models[model_id] = {
                "model_id": model_id,
                "make": make,
                "model": model,
                "trim": "",
                "body_type": "",
                "segment": "",
                "n_observations": n,
            }
            self.aliases[norm_key] = (model_id, 1.0)
            self._by_id[f"{make}|{model}"] = model_id

        # Add the unqualified model name as an alias too (helps cross-source typos).
        for mid, row in self.models.items():
            alias = normalize_arabic(row["model"])
            if alias and alias not in self.aliases:
                self.aliases[alias] = (mid, 0.95)
        return self

    def map(self, make_raw: str | None, model_raw: str | None) -> tuple[int | None, float]:
        """Exact alias hit -> accept; else fuzzy s>=0.85 -> accept; else unmapped."""
        k = self.key(make_raw, model_raw)
        if not k:
            return None, 0.0
        if k in self.aliases:
            mid, conf = self.aliases[k]
            return mid, conf
        best_mid, best_s = None, 0.0
        for alias, (mid, _) in self.aliases.items():
            s = similarity(k, alias)
            if s > best_s:
                best_mid, best_s = mid, s
        if best_s >= FUZZY_THRESHOLD:
            return best_mid, best_s
        return None, best_s

    def canonical(self, model_id: int | None) -> tuple[str | None, str | None, str | None]:
        if model_id is None or model_id not in self.models:
            return None, None, None
        row = self.models[model_id]
        return row["make"], row["model"], row["trim"] or None

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "models.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(next(iter(self.models.values())).keys()))
            w.writeheader()
            w.writerows(self.models.values())
        with (directory / "aliases.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["normalized_alias", "model_id", "confidence"])
            for alias, (mid, conf) in sorted(self.aliases.items()):
                w.writerow([alias, mid, f"{conf:.3f}"])

    @classmethod
    def load(cls, directory: Path) -> ModelDictionary:
        directory = Path(directory)
        d = cls()
        with (directory / "models.csv").open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["model_id"] = int(row["model_id"])
                row["n_observations"] = int(row["n_observations"])
                d.models[row["model_id"]] = row
        with (directory / "aliases.csv").open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d.aliases[row["normalized_alias"]] = (
                    int(row["model_id"]),
                    float(row["confidence"]),
                )
        return d

"""Linkage stage: candidates -> comparison -> FS+EM -> thresholds -> clusters."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from autolens.common.stage import RunContext, StageResult
from autolens.linkage.blocking import generate_candidates, reduction_ratio
from autolens.linkage.cluster import assign_vehicle_ids, link_rows
from autolens.linkage.comparison import build_matrix
from autolens.linkage.evaluate import bootstrap_ci, choose_thresholds, prf
from autolens.linkage.fs import fs_em, match_weight
from autolens.linkage.labels import build_labels, save_labels
from autolens.linkage.supervised import cross_validated_scores


def _load_listings(ctx: RunContext, run_date) -> list[dict]:
    rows = ctx.db.query(
        "SELECT * FROM staging_normalized_listing WHERE scrape_date=?", (str(run_date),)
    )
    # pHash only from real listing photos. Placeholder / open-source / synthetic images are
    # assigned from the listing's own attributes, so using them would leak the blocking
    # attributes into photo_match and inflate match weights.
    statuses = tuple(getattr(ctx.settings, "photo_match_statuses", ("fetched", "promoted")))
    marks = ",".join("?" for _ in statuses)
    hashes = {
        r["listing_key"]: r["phash"]
        for r in ctx.db.query(
            "SELECT listing_key, phash FROM staging_image_fetch "
            f"WHERE position=0 AND status IN ({marks})",
            statuses,
        )
    }
    out = []
    for r in rows:
        d = dict(r)
        d["listing_key"] = f"{d['source']}:{d['source_listing_id']}"
        d["desc_vec"] = None  # no descriptions in the supplied archives (M4)
        d["phash"] = hashes.get(d["listing_key"])
        out.append(d)
    return out


def _previous_mapping(ctx: RunContext) -> dict[str, int]:
    rows = ctx.db.query("SELECT listing_key, vehicle_id FROM core_vehicle_link")
    return {r["listing_key"]: r["vehicle_id"] for r in rows}


def _singleton_result(
    run_date,
    ctx: RunContext,
    listings: list[dict],
    warnings: list[str],
    reason: str,
    n_pairs: int,
    truncated: bool,
) -> StageResult:
    """No usable evidence to link anything: keep every listing as its own vehicle."""
    previous = _previous_mapping(ctx)
    keys = [r["listing_key"] for r in listings]
    mapping, merges = assign_vehicle_ids([], previous, all_keys=keys, max_cluster=9)
    link_run_id = f"link-{run_date}"
    ctx.db.insert_many("core_vehicle_link", link_rows(mapping, [], link_run_id))
    warnings = [*warnings, f"{reason}: no links accepted, every listing is its own vehicle"]
    return StageResult(
        "linkage",
        run_date,
        len(listings),
        len(mapping),
        warnings,
        {
            "n_pairs": n_pairs,
            "n_clusters": len(set(mapping.values())),
            "candidate_pairs_truncated": truncated,
        },
    )


def run_linkage(run_date, ctx: RunContext, max_pairs: int | None = None) -> StageResult:
    max_pairs = max_pairs or int(getattr(ctx.settings, "max_candidate_pairs", 2_000_000))
    listings = _load_listings(ctx, run_date)
    n = len(listings)
    if n == 0:
        return StageResult("linkage", run_date, 0, 0, ["no_normalized_listings"])

    pairs = generate_candidates(listings, max_pairs=max_pairs)
    warnings: list[str] = []
    truncated = len(pairs) >= max_pairs
    if truncated:
        warnings.append(f"candidate_pairs_truncated: capped at {max_pairs}; blocking is incomplete")
        ctx.log.warning("candidate pairs truncated at %d", max_pairs)
    photo_active = sum(1 for r in listings if r["phash"])
    if photo_active == 0:
        warnings.append("photo_match_inactive: no real listing photos, feature treated as missing")
    if not pairs:
        return _singleton_result(run_date, ctx, listings, warnings, "no_candidate_pairs", 0, False)
    G, feature_names = build_matrix(listings, pairs)
    m, u, prior, posterior = fs_em(G, p0=0.001, m0=0.9, u0=0.1)
    weights = match_weight(G, m, u)
    rr = reduction_ratio(len(pairs), n)

    # Evaluation set (provisional silver labels + human labelling view).
    labels = build_labels(listings, pairs, weights)
    if labels.empty:
        return _singleton_result(
            run_date, ctx, listings, warnings, "no_labelled_pairs", len(pairs), truncated
        )
    labelled_pairs = [pairs[int(r.pair_id)] for r in labels.itertuples(index=False)]
    y = labels["label"].to_numpy().astype(int)

    # Supervised comparators on the same comparison vector (8.7.3).
    X = np.where(G >= 0, G, 0).astype(float)
    X = np.column_stack([X, weights])
    sup = cross_validated_scores(X[labels["pair_id"].to_numpy()], y, labelled_pairs)

    # Thresholds and headline metrics for FS (evaluated on the labelled subset).
    label_ids = labels["pair_id"].to_numpy()
    label_scores = weights[label_ids]
    upper, lower = choose_thresholds(y, label_scores)
    fs_pred = label_scores >= upper
    fs_metrics = prf(y, fs_pred)
    fs_ci = bootstrap_ci(y, label_scores, upper)

    review_band = np.mean((weights >= lower) & (weights < upper))
    results = {
        "n_listings": n,
        "n_candidate_pairs": len(pairs),
        "reduction_ratio": rr,
        "features": feature_names,
        "fs_m": m.tolist(),
        "fs_u": u.tolist(),
        "fs_prior": prior,
        "t_upper": upper,
        "t_lower": lower,
        "review_band_share": float(review_band),
        "fs_metrics": fs_metrics,
        "fs_ci95": {k: list(v) for k, v in fs_ci.items()},
        "supervised": {
            k: {kk: vv for kk, vv in v.items() if kk != "oof_scores"} for k, v in sup.items()
        },
        "candidate_pairs_truncated": truncated,
        "listings_with_real_photo_hash": photo_active,
        "n_labelled_pairs": len(labels),
        "label_positive_rate": float(y.mean()),
        "evaluation_status": "provisional: silver labels derived from the same features",
        "human_ground_truth_available": False,
    }

    # Acceptance -> edges -> stable clusters.
    accepted = [r for r, w in enumerate(weights) if w >= upper]
    edges = [
        (
            listings[pairs[r][0]]["listing_key"],
            listings[pairs[r][1]]["listing_key"],
            float(weights[r]),
        )
        for r in accepted
    ]
    previous = _previous_mapping(ctx)
    mapping, merges = assign_vehicle_ids(
        edges, previous, all_keys=[r["listing_key"] for r in listings], max_cluster=9
    )
    # Deterministic per run_date so re-running the same day is idempotent (15.8).
    link_run_id = f"link-{run_date}"
    ctx.db.insert_many("core_vehicle_link", link_rows(mapping, edges, link_run_id))
    ctx.db.insert_many(
        "core_vehicle_id_merge",
        [
            {
                "old_id": old,
                "new_id": new,
                "merged_at": datetime.now(UTC).isoformat(),
            }
            for old, new in merges
        ],
    )

    (ctx.settings.root / "data_labels").mkdir(parents=True, exist_ok=True)
    ctx.settings.output_dir.mkdir(parents=True, exist_ok=True)
    saved_label_path = save_labels(
        labels, ctx.settings.root / "data_labels" / "linkage_pairs_v1.parquet"
    )
    # Never call automatically generated labels human ground truth. Provide a
    # separate, blank annotation sheet for two independent reviewers.
    review = labels[["listing_key_a", "listing_key_b", "source_pair", "match_weight"]].copy()
    review["reviewer_1_label"] = ""
    review["reviewer_2_label"] = ""
    review["adjudicated_label"] = ""
    review.to_csv(ctx.settings.root / "data_labels" / "human_review_template.csv", index=False)
    results["evaluation_status"] = "provisional_silver_labels_only"
    results["human_ground_truth_available"] = False
    results["saved_silver_labels"] = saved_label_path.name
    labels.to_csv(ctx.settings.output_dir / "labelled_pairs.csv", index=False)
    pd.DataFrame({"feature": feature_names, "m": m, "u": u}).to_csv(
        ctx.settings.output_dir / "fs_parameters.csv", index=False
    )
    (ctx.settings.output_dir / "linkage_metrics.json").write_text(json.dumps(results, indent=2))
    ctx.log.info(
        "linkage: pairs=%d accepted=%d clusters=%d P=%.3f R=%.3f F1=%.3f",
        len(pairs),
        len(edges),
        len(set(mapping.values())),
        fs_metrics["precision"],
        fs_metrics["recall"],
        fs_metrics["f1"],
    )
    return StageResult(
        "linkage",
        run_date,
        n,
        len(mapping),
        warnings + ["evaluation_provisional: silver labels only, no human ground truth"],
        {
            "n_pairs": len(pairs),
            "n_clusters": len(set(mapping.values())),
            "f1_silver": fs_metrics["f1"],
            "t_upper": upper,
            "candidate_pairs_truncated": truncated,
        },
    )

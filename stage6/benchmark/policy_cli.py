from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..decision.calibration import ThresholdPolicy, calibration_report, normalize_threshold_candidates
from ..decision.jev import JevDecisionEngine
from ..decision.rule import RuleDecisionEngine
from ..decision.zhipu import ZhipuDecisionEngine
from ..decision.schema import DecisionEngineUnavailable
from .fixture import FixtureGLMEngine, FixtureJevEngine
from .runner import load_jsonl, run_engine, run_threshold_sweep
from .policy import summarize_policy


def build_engine(name: str, mode: str):
    if name == "rule":
        return RuleDecisionEngine()
    if name == "glm":
        return FixtureGLMEngine(error_ids={"intent-04"}) if mode == "fixture" else ZhipuDecisionEngine()
    if name == "jev":
        return FixtureJevEngine(error_ids={"tool-04"}) if mode == "fixture" else JevDecisionEngine()
    raise ValueError(name)


def _parse_thresholds(value: str) -> list[float]:
    return [round(float(v.strip()), 3) for v in value.split(",") if v.strip()]


def _sha256_jsonl(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_frozen_policy(path: str | Path) -> ThresholdPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("policy_type") != "stage6_threshold_policy":
        raise ValueError("invalid frozen policy: policy_type mismatch")
    policy = payload.get("policy") or {}
    auto_threshold = float(policy["auto_threshold"])
    selection = payload.get("selection") or {}
    candidates = selection.get("threshold_candidates")
    if not candidates:
        raise ValueError("invalid frozen policy: threshold_candidates are required")
    normalized = normalize_threshold_candidates(candidates)
    if round(auto_threshold, 3) not in normalized:
        raise ValueError("invalid frozen policy: auto_threshold is not one of threshold_candidates")
    return ThresholdPolicy(
        auto_threshold=auto_threshold,
        review_threshold=float(policy["review_threshold"]),
    )


def _write_frozen_policy(
    path: str | Path,
    *,
    engine: str,
    fallback_engine: str,
    policy: ThresholdPolicy,
    validation_dataset: str | Path,
    calibration: dict,
    thresholds: list[float],
) -> None:
    out = {
        "policy_type": "stage6_threshold_policy",
        "version": 2,
        "engine": engine,
        "fallback_engine": fallback_engine,
        "selected_on": "validation",
        "dataset": str(validation_dataset),
        "dataset_sha256": _sha256_jsonl(validation_dataset),
        "policy": {
            "auto_threshold": policy.auto_threshold,
            "review_threshold": policy.review_threshold,
        },
        "selection": {
            "threshold_candidates": thresholds,
            "candidate_source": "actual_sweep",
            "min_auto_accuracy": calibration.get("min_auto_accuracy"),
            "min_auto_coverage": calibration.get("min_auto_coverage"),
            "review_gap": calibration.get("review_gap"),
        },
        "calibration_snapshot": {
            "cases": calibration.get("cases"),
            "auto_accuracy": calibration.get("auto_accuracy"),
            "auto_coverage": calibration.get("auto_coverage"),
        },
        "warning": "Frozen policy. Do not recalibrate or edit for the Test Set.",
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage6-C threshold calibration, freeze, and frozen Test evaluation")
    default_dataset = str(Path(__file__).resolve().parents[1] / "datasets" / "decision_benchmark.jsonl")
    ap.add_argument("--dataset", default=default_dataset, help="Validation dataset (backward-compatible alias)")
    ap.add_argument("--validation-dataset", default=None)
    ap.add_argument("--test-dataset", default=None, help="Frozen Test Set; must be evaluated with --policy-file")
    ap.add_argument("--policy-file", default=None, help="Frozen policy JSON produced from Validation")
    ap.add_argument("--freeze-policy", default=None, help="Write frozen policy JSON after Validation calibration")
    ap.add_argument("--mode", choices=["fixture", "real"], default="fixture")
    ap.add_argument("--engine", choices=["rule", "glm", "jev"], default="jev")
    ap.add_argument("--fallback-engine", choices=["none", "rule", "glm", "jev"], default="none")
    ap.add_argument("--thresholds", default="0.50,0.60,0.70,0.80,0.90,0.95")
    ap.add_argument("--review-gap", type=float, default=0.20)
    ap.add_argument("--min-auto-accuracy", type=float, default=0.95)
    ap.add_argument("--min-auto-coverage", type=float, default=0.60)
    ap.add_argument("--output")
    args = ap.parse_args()

    validation_path = args.validation_dataset or args.dataset
    test_cases = load_jsonl(args.test_dataset) if args.test_dataset else None
    thresholds = normalize_threshold_candidates(_parse_thresholds(args.thresholds))

    if args.test_dataset and not args.policy_file:
        raise SystemExit("Test evaluation requires --policy-file; do not recalibrate on Test Set")
    if args.policy_file and not args.test_dataset:
        raise SystemExit("--policy-file is a frozen Test policy and requires --test-dataset")
    if args.freeze_policy and args.policy_file:
        raise SystemExit("use --freeze-policy during Validation OR --policy-file during Test, not both")

    try:
        engine = build_engine(args.engine, args.mode)
        fallback = None if args.fallback_engine == "none" else build_engine(args.fallback_engine, args.mode)
    except DecisionEngineUnavailable as exc:
        print(f"engine unavailable: {exc}")
        return 2

    report: dict = {
        "engine": engine.name,
        "fallback_engine": fallback.name if fallback is not None else None,
        "experiment": {
            "mode": "test_frozen" if args.test_dataset else "validation_calibration",
            "policy_frozen": bool(args.policy_file),
        },
    }

    if args.test_dataset:
        validation_cases = None
        policy = _load_frozen_policy(args.policy_file)
        test_rows = run_engine(
            engine,
            test_cases,
            fallback_engine=fallback,
            policy=policy,
        )
        summary = summarize_policy(test_rows, test_rows)["overall"]
        report.update({
            "policy_file": str(args.policy_file),
            "frozen_policy": {
                "auto_threshold": policy.auto_threshold,
                "review_threshold": policy.review_threshold,
            },
            "test": {
                "cases": len(test_cases),
                "metrics": summary,
            },
        })
        # Never include a Validation recalibration section in frozen Test mode.
        validation_path = None
    else:
        validation_cases = load_jsonl(validation_path)
        raw_rows = run_engine(engine, validation_cases, fallback_engine=None)
        calibration = calibration_report(
            raw_rows,
            min_auto_accuracy=args.min_auto_accuracy,
            min_auto_coverage=args.min_auto_coverage,
            review_gap=args.review_gap,
            threshold_candidates=thresholds,
        )
        calibration.update({
            "min_auto_accuracy": args.min_auto_accuracy,
            "min_auto_coverage": args.min_auto_coverage,
            "review_gap": args.review_gap,
        })
        sweep = run_threshold_sweep(
            engine,
            validation_cases,
            fallback_engine=fallback,
            thresholds=thresholds,
            review_gap=args.review_gap,
        )
        policy = ThresholdPolicy(
            auto_threshold=calibration["auto_threshold"],
            review_threshold=calibration["review_threshold"],
        )
        if policy.auto_threshold not in thresholds:
            raise AssertionError("Calibration selected a threshold outside the actual sweep candidates")
        report.update({
            "validation_cases": len(validation_cases),
            "calibration": calibration,
            "threshold_sweep": sweep["sweep"],
            "frozen_policy": {
                "auto_threshold": policy.auto_threshold,
                "review_threshold": policy.review_threshold,
            },
        })
        if args.freeze_policy:
            _write_frozen_policy(
                args.freeze_policy,
                engine=engine.name,
                fallback_engine=fallback.name if fallback is not None else "none",
                policy=policy,
                validation_dataset=validation_path,
                calibration=calibration,
                thresholds=thresholds,
            )
            report["freeze_policy_file"] = str(args.freeze_policy)

    # Cost is only meaningful when every actually executed engine has a configured price.
    pricing_rows = test_rows if args.test_dataset else raw_rows
    pricing_engines: dict[str, dict] = {}
    if not args.test_dataset and 'sweep' in locals():
        for engine_name, item in (sweep.get("pricing") or {}).items():
            pricing_engines[engine_name] = dict(item)
    for row in pricing_rows:
        meta = row.get("metadata", {}) or {}
        engine_name = str(row.get("engine", engine.name))
        pricing_engines[engine_name] = {
            "configured": bool(meta.get("pricing_configured", True)),
            "input_cost_per_million": meta.get("input_cost_per_million"),
            "output_cost_per_million": meta.get("output_cost_per_million"),
            "currency": meta.get("pricing_currency", "UNSPECIFIED"),
        }
        fallback_record = row.get("fallback_record") or {}
        if fallback_record:
            fb_name = str(fallback_record.get("engine", "unknown"))
            pricing_engines[fb_name] = {
                "configured": bool(fallback_record.get("pricing_configured", True)),
                "input_cost_per_million": fallback_record.get("input_cost_per_million"),
                "output_cost_per_million": fallback_record.get("output_cost_per_million"),
            }
    report["pricing"] = {
        "configured": all(item["configured"] for item in pricing_engines.values()) if pricing_engines else True,
        "engines": pricing_engines,
        "note": "Cost is reported as null when any executed engine lacks configured pricing.",
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

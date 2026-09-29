from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .fixture import FixtureGLMEngine, FixtureJevEngine
from .runner import load_jsonl, run_engine
from ..decision.jev import JevDecisionEngine
from ..decision.rule import RuleDecisionEngine
from ..decision.zhipu import ZhipuDecisionEngine
from ..decision.schema import DecisionEngineUnavailable


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage6 Rule / GLM / JEV decision benchmark")
    ap.add_argument("--dataset", default=str(Path(__file__).resolve().parents[1] / "datasets" / "decision_benchmark.jsonl"))
    ap.add_argument("--mode", choices=["fixture", "real", "rule-only"], default="fixture")
    ap.add_argument("--engine", choices=["all", "rule", "glm", "jev"], default="all")
    ap.add_argument("--output")
    ap.add_argument("--fallback-engine", choices=["none", "rule", "glm", "jev"], default="none",
                    help="fallback engine for low-confidence JEV decisions")
    args = ap.parse_args()
    cases = load_jsonl(args.dataset)

    engines = {}
    if args.engine in {"all", "rule"}:
        engines["rule"] = RuleDecisionEngine()
    if args.engine in {"all", "glm"}:
        if args.mode == "fixture":
            engines["glm"] = FixtureGLMEngine(error_ids={"intent-04"})
        elif args.mode == "real":
            try:
                engines["glm"] = ZhipuDecisionEngine()
            except DecisionEngineUnavailable as exc:
                print(f"GLM unavailable: {exc}")
                return 2
    if args.engine in {"all", "jev"}:
        if args.mode == "fixture":
            engines["jev"] = FixtureJevEngine(error_ids={"tool-04"})
        elif args.mode == "real":
            try:
                engines["jev"] = JevDecisionEngine()
            except DecisionEngineUnavailable as exc:
                print(f"JEV unavailable: {exc}")
                return 2

    from .metrics import aggregate
    fallback_engines = {}
    if args.fallback_engine != "none" and "jev" in engines:
        if args.fallback_engine == "rule":
            fallback_engines["jev"] = engines.get("rule") or RuleDecisionEngine()
        elif args.fallback_engine == "glm":
            if "glm" in engines:
                fallback_engines["jev"] = engines["glm"]
            elif args.mode == "fixture":
                fallback_engines["jev"] = FixtureGLMEngine(error_ids=set())
            else:
                try:
                    fallback_engines["jev"] = ZhipuDecisionEngine()
                except DecisionEngineUnavailable as exc:
                    print(f"GLM fallback unavailable: {exc}")
                    return 2
        elif args.fallback_engine == "jev":
            print("JEV cannot fall back to itself")
            return 2
    report = {}
    for name, engine in engines.items():
        rows = run_engine(engine, cases, fallback_engine=fallback_engines.get(name))
        report[name] = {"metrics": aggregate(rows), "rows": rows}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

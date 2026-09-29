from __future__ import annotations

import argparse
import json

from .benchmark.fixture import FixtureGLMEngine, FixtureJevEngine
from .decision.jev import JevDecisionEngine
from .decision.rule import RuleDecisionEngine
from .decision.zhipu import ZhipuDecisionEngine
from .decision.schema import DecisionEngineUnavailable, DecisionTask


def _engine(name: str):
    if name == "rule":
        return RuleDecisionEngine()
    if name == "glm":
        return ZhipuDecisionEngine()
    if name == "jev":
        return JevDecisionEngine()
    raise ValueError(name)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage6 decision layer")
    ap.add_argument("--engine", choices=["rule", "glm", "jev"], default="rule")
    ap.add_argument("--task-type", choices=["skill", "tool", "intent"], default="skill")
    ap.add_argument("--text", required=True)
    ap.add_argument("--options", required=True, help='JSON object, e.g. {"question-followup":"追问候选人回答"}')
    args = ap.parse_args()
    options = json.loads(args.options)
    engine = _engine(args.engine)
    task = DecisionTask(
        task_id="cli",
        task_type=args.task_type,
        state=args.text,
        options=options,
    )
    try:
        result = engine.decide(task)
    except DecisionEngineUnavailable as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "ok": True,
        "engine": result.engine,
        "choice": result.choice,
        "probabilities": result.probabilities,
        "confidence": result.confidence,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": result.cost,
        "route": "auto" if result.confidence >= 0.90 else "review" if result.confidence >= 0.70 else "fallback",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

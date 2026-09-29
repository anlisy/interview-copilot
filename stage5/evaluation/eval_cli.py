from __future__ import annotations
import argparse
import json
from pathlib import Path
import yaml

from .evaluator import evaluate
from .gate import check_gate
from .golden import load_jsonl, validate_cases


def main() -> int:
    ap = argparse.ArgumentParser(description="Interview Copilot Stage5 Evaluation")
    ap.add_argument("--golden", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    golden = load_jsonl(args.golden)
    predictions = load_jsonl(args.predictions)
    validate_cases(golden)
    validate_cases(predictions, prediction=True)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if args.baseline else None

    result = evaluate(golden, predictions, args.k)
    gate = check_gate(result, config, baseline)
    result["gate"] = {"passed": gate.passed, "failures": gate.failures}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if gate.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

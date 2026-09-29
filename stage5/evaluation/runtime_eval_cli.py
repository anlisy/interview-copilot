from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml

from .evaluator import evaluate
from .gate import check_gate
from .golden import load_jsonl, validate_cases
from .trace_adapter import build_prediction_from_trace


def _load_session_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("session-map must be a JSON object: {golden_id: session_id}")
    return {str(k): str(v) for k, v in data.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage5 evaluation with real Stage1 trace evidence")
    ap.add_argument("--traces", required=True)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--predictions", required=True, help="semantic/annotation predictions JSONL")
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline")
    ap.add_argument("--session-map")
    ap.add_argument("--output", help="write merged runtime predictions JSONL")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    golden = load_jsonl(args.golden)
    predictions = load_jsonl(args.predictions)
    validate_cases(golden)
    validate_cases(predictions, prediction=True)
    pred_by_id = {row["id"]: row for row in predictions}
    session_map = _load_session_map(args.session_map)

    merged: list[dict] = []
    for case in golden:
        cid = case["id"]
        base = pred_by_id.get(cid, {"id": cid})
        merged.append(
            build_prediction_from_trace(
                cid,
                args.traces,
                base_prediction=base,
                session_id=session_map.get(cid, cid),
            )
        )

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8")) if args.baseline else None
    result = evaluate(golden, merged, args.k)
    gate = check_gate(result, config, baseline)
    result["gate"] = {"passed": gate.passed, "failures": gate.failures}
    result["trace_source"] = str(Path(args.traces))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in merged) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if gate.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

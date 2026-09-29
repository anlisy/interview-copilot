from __future__ import annotations
import argparse
import json
from pathlib import Path


def calibrate(rows: list[dict]) -> dict:
    """Validation Set 上选择 F1 最大阈值；同分优先 precision。"""
    candidates = sorted({round(float(r["similarity"]), 4) for r in rows})
    best = None
    for threshold in candidates:
        tp = fp = fn = 0
        for row in rows:
            pred = float(row["similarity"]) >= threshold
            gold = int(row["label"]) == 1
            tp += int(pred and gold)
            fp += int(pred and not gold)
            fn += int((not pred) and gold)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        item = {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1}
        if best is None or (f1, precision) > (best["f1"], best["precision"]):
            best = item
    return best or {"threshold": 0.55, "precision": 0.0, "recall": 0.0, "f1": 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True, help="Validation JSONL: similarity,label")
    args = ap.parse_args()
    rows = [
        json.loads(line)
        for line in Path(args.pairs).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(json.dumps(calibrate(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

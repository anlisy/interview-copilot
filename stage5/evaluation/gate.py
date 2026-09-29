from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping


@dataclass
class GateResult:
    passed: bool
    failures: list[str]


def _get(metrics: Mapping, path: str):
    cur = metrics
    for part in path.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_gate(current: Mapping, config: Mapping, baseline: Mapping | None = None) -> GateResult:
    failures: list[str] = []

    for path, rule in config.get("absolute", {}).items():
        value = _get(current, path)
        if value is None:
            continue
        direction = rule["direction"]
        threshold = float(rule["threshold"])
        ok = value >= threshold if direction == "max" else value <= threshold
        if not ok:
            failures.append(f"absolute {path}: value={value:.6f}, threshold={threshold:.6f}")

    if baseline:
        for path, rule in config.get("relative", {}).items():
            cur = _get(current, path)
            base = _get(baseline, path)
            if cur is None or base in (None, 0):
                continue
            direction = rule["direction"]
            if direction == "max":
                drop = (base - cur) / abs(base)
                if drop > float(rule.get("max_drop", 0.0)):
                    failures.append(f"relative {path}: drop={drop:.2%} > {float(rule.get('max_drop', 0.0)):.2%}")
            else:
                increase = (cur - base) / abs(base)
                if increase > float(rule.get("max_increase", 0.0)):
                    failures.append(f"relative {path}: increase={increase:.2%} > {float(rule.get('max_increase', 0.0)):.2%}")

    return GateResult(not failures, failures)

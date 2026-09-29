from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

_RUNTIME_FIELDS = {
    "tool_selected",
    "invalid_tool_call",
    "trajectory_success",
    "retried",
    "max_step_hit",
    "latency_ms",
    "tokens",
    "cost",
    "memory_ids",
    "temporal_state_ok",
    "stale_memory",
    "unsupported_memory",
    "ground_truth_leakage",
    "unauthorized_tool_call",
    "prompt_injection_bypass",
}

_ERROR_CODES = {
    "unknown_tool",
    "policy_denied",
    "eval_tool_denied",
    "eval_only_denied",
    "agent_acl_denied",
    "action_acl_denied",
    "no_acl",
    "action_acl_missing",
    "input_schema_invalid",
    "output_schema_invalid",
    "tool_unavailable",
}

_MAX_STEP_RE = re.compile(r"最大执行步数|max[_ -]?step", re.I)
_UNAUTHORIZED_RE = re.compile(r"unauthori[sz]ed|无权|禁止|ACL|policy_denied|agent_acl_denied|action_acl_denied|no_acl", re.I)
_GROUND_TRUTH_RE = re.compile(r"ground[_ -]?truth|标准答案|真实面经", re.I)
_INJECTION_RE = re.compile(r"prompt[_ -]?injection|注入绕过|越权提示", re.I)


def safe_session_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return value[:120] or "session"


def load_trace_events(root: str | Path, session_id: str) -> list[dict[str, Any]]:
    path = Path(root) / f"{safe_session_id(session_id)}.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid trace JSONL at {path}:{lineno}") from exc
        if isinstance(row, dict):
            events.append(row)
    return events


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _collect_strings(value: Any) -> list[str]:
    out: list[str] = []
    for item in _walk(value):
        for v in item.values():
            if isinstance(v, str):
                out.append(v)
    return out


def _collect_memory_ids(events: Iterable[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for event in events:
        for item in _walk(event):
            record_id = item.get("record_id")
            if isinstance(record_id, str) and record_id and record_id not in seen:
                seen.add(record_id)
                ids.append(record_id)
    return ids


def _last_tool(events: Iterable[dict[str, Any]]) -> str | None:
    tool: str | None = None
    saw_action = False
    for event in events:
        if event.get("event") == "before_action":
            saw_action = True
        if isinstance(event.get("tool"), str) and event.get("tool"):
            tool = event["tool"]
        decision = event.get("decision_summary")
        if isinstance(decision, dict) and isinstance(decision.get("tool"), str):
            tool = decision["tool"]
    return tool if tool is not None else ("none" if saw_action else None)


def _sum_numeric(events: Iterable[dict[str, Any]], field: str) -> float:
    total = 0.0
    for event in events:
        value = event.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += float(value)
    return total


def build_runtime_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    before_actions = [e for e in events if e.get("event") == "before_action"]
    after_actions = [e for e in events if e.get("event") == "after_action"]
    violations = [e for e in events if e.get("event") == "harness_violation"]
    usage = [e for e in events if e.get("event") == "usage"]

    errors: list[str] = []
    for event in events:
        code = event.get("error_code")
        if isinstance(code, str):
            errors.append(code)
        message = event.get("message")
        if isinstance(message, str):
            errors.append(message)

    retries = False
    for event in events:
        attempts = event.get("attempts")
        if isinstance(attempts, (int, float)) and attempts > 1:
            retries = True
        for nested in _walk(event):
            attempts = nested.get("attempts")
            if isinstance(attempts, (int, float)) and attempts > 1:
                retries = True

    statuses = [e.get("status") for e in after_actions if e.get("status") is not None]
    trajectory_success = bool(after_actions) and statuses[-1] == "success"

    latency = _sum_numeric(after_actions, "latency_ms")
    tokens = _sum_numeric(usage, "total_tokens")
    cost = _sum_numeric(usage, "cost_usd")

    unauthorized = any(_UNAUTHORIZED_RE.search(x) for x in errors if isinstance(x, str))
    invalid_tool = any(code in errors for code in _ERROR_CODES) or unauthorized
    max_step_hit = any(_MAX_STEP_RE.search(x) for x in errors if isinstance(x, str))
    ground_truth = any(
        bool(event.get("ground_truth_leakage"))
        or (event.get("event") in {"tool_result", "tool_call"} and event.get("tool") == "ground_truth_search" and event.get("ok") is True)
        for event in events
    )
    injection = any(bool(event.get("prompt_injection_bypass")) for event in events)

    evidence: dict[str, Any] = {
        "tool_selected": _last_tool(events),
        "invalid_tool_call": invalid_tool,
        "trajectory_success": trajectory_success,
        "retried": retries,
        "max_step_hit": max_step_hit,
        "latency_ms": round(latency, 2),
        "tokens": int(tokens),
        "cost": round(cost, 8),
        "memory_ids": _collect_memory_ids(events),
        "ground_truth_leakage": ground_truth,
        "unauthorized_tool_call": unauthorized,
        "prompt_injection_bypass": injection,
    }

    explicit_fields: dict[str, bool] = {}
    for event in events:
        for key in ("temporal_state_ok", "stale_memory", "unsupported_memory"):
            if key in event and isinstance(event[key], bool):
                explicit_fields[key] = explicit_fields.get(key, False) or event[key]
    evidence.update(explicit_fields)
    return evidence


def merge_runtime_evidence(prediction: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    merged = dict(prediction)
    for field in _RUNTIME_FIELDS:
        if field in evidence:
            merged[field] = evidence[field]
    return merged


def build_prediction_from_trace(
    case_id: str,
    trace_root: str | Path,
    base_prediction: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    session_id = session_id or case_id
    events = load_trace_events(trace_root, session_id)
    prediction = {"id": case_id}
    if base_prediction:
        prediction.update(base_prediction)
    if not events:
        return prediction
    evidence = build_runtime_evidence(events)
    prediction.update({"id": case_id})
    return merge_runtime_evidence(prediction, evidence)

import json
from dataclasses import dataclass
from pathlib import Path
import time
import pytest

from agent_runtime.workflow import Workflow
from agent_runtime.harness import Harness, HarnessContext, HarnessViolation
from agent_runtime.trace import TraceRecorder
from agent_runtime.orchestrator import Orchestrator, DecisionError

ROOT = Path(__file__).resolve().parents[1]


def make_harness(tmp_path):
    wf = Workflow.load(ROOT / "core" / "workflow.yaml")
    return wf, Harness(wf, TraceRecorder(tmp_path / "trace"))


def test_workflow():
    wf = Workflow.load(ROOT / "core" / "workflow.yaml")
    assert wf.is_agent_allowed("INIT", "interviewer")
    assert wf.is_action_allowed("INIT", "diagnose")
    assert wf.can_transition("INIT", "DIAGNOSIS")
    assert not wf.is_action_allowed("INIT", "review")
    assert wf.max_steps() == 60
    assert wf.token_budget() == 24000




def test_score_state_flow():
    wf = Workflow.load(ROOT / "core" / "workflow.yaml")
    assert wf.is_action_allowed("ASKING", "score")
    assert wf.is_action_allowed("FOLLOWUP", "score")
    assert not wf.is_action_allowed("SCORING", "score")
    assert wf.can_transition("ASKING", "SCORING")
    assert wf.can_transition("SCORING", "FOLLOWUP")
    assert wf.can_transition("FOLLOWUP", "SCORING")

def test_eval_denies_ground_truth(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s1", stage="SCORING", eval_mode=True)
    with pytest.raises(HarnessViolation):
        h.before(ctx, "interviewer", "followup", tool="nowcoder_search")


def test_illegal_tool_denied_by_stage(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s1", stage="INIT")
    with pytest.raises(HarnessViolation):
        h.before(ctx, "interviewer", "diagnose", tool="memory_search")


def test_illegal_transition(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s2")
    with pytest.raises(HarnessViolation):
        h.transition(ctx, "REVIEWING")


def test_session_version_conflict(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s3")
    result = h.execute(ctx, "interviewer", "diagnose", lambda: {"ok": True}, expected_session_version=0)
    assert result["ok"] is True
    assert ctx.session_version == 1
    with pytest.raises(HarnessViolation):
        h.execute(ctx, "interviewer", "diagnose", lambda: {"ok": True}, expected_session_version=0)


def test_followup_limit(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s4", stage="SCORING")
    h.execute(ctx, "interviewer", "followup", lambda: {})
    h.execute(ctx, "interviewer", "followup", lambda: {})
    assert ctx.followup_count == 2
    with pytest.raises(HarnessViolation):
        h.execute(ctx, "interviewer", "followup", lambda: {})


def test_token_budget(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s5")
    h.consume_usage(ctx, input_tokens=23999)
    with pytest.raises(HarnessViolation):
        h.consume_usage(ctx, output_tokens=2)


def test_cost_budget(tmp_path, monkeypatch):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s6")
    h.consume_usage(ctx, cost_usd=0.99)
    with pytest.raises(HarnessViolation):
        h.consume_usage(ctx, cost_usd=0.02)


def test_timeout(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s7")
    old = wf.actions["diagnose"]["timeout_seconds"]
    wf.actions["diagnose"]["timeout_seconds"] = 0.02
    try:
        with pytest.raises(HarnessViolation):
            h.execute(ctx, "interviewer", "diagnose", lambda: time.sleep(0.05))
    finally:
        wf.actions["diagnose"]["timeout_seconds"] = old


def test_result_schema(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s8", stage="ASKING")
    with pytest.raises(HarnessViolation):
        h.execute(ctx, "scorer", "score", lambda: {"comment": "x"})




def test_result_schema_accepts_dataclass(tmp_path):
    @dataclass
    class ScoreResult:
        total: float
        comment: str = "ok"

    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s8-dataclass", stage="ASKING")
    result = h.execute(ctx, "scorer", "score", lambda: ScoreResult(total=4.2))
    assert result.total == 4.2

def test_trace_contains_core_events(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s9")
    h.execute(ctx, "interviewer", "diagnose", lambda: {"ok": True})
    h.transition(ctx, "DIAGNOSIS")
    events = [
        json.loads(x)
        for x in (tmp_path / "trace" / "s9.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {e["event"] for e in events} >= {"before_action", "after_action", "transition"}
    assert all(e["session_id"] == "s9" for e in events)


def test_orchestrator_rejects_bad_decision(monkeypatch, tmp_path):
    class FakeClient:
        model = "fake"
        def chat(self, messages, **kwargs):
            from agent_runtime.zhipu_client import LLMResponse
            return LLMResponse('{"agent":"reviewer","action":"review","session_version":0}', "fake")

    o = Orchestrator(ROOT / "core" / "workflow.yaml", "s10", client=FakeClient())
    with pytest.raises(DecisionError):
        o.decide("完成诊断", {"x": 1})


def test_workflow_rejects_unknown_action(tmp_path):
    bad = {
        "version": 1,
        "stages": {"INIT": {"allowed_agents": ["interviewer"], "allowed_actions": ["missing"], "next_stages": []}},
        "actions": {},
    }
    import yaml
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(Exception):
        Workflow.load(path)


def test_illegal_next_stage_is_rejected_before_handler(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s10-next")
    called = []
    with pytest.raises(HarnessViolation):
        h.execute(ctx, "interviewer", "diagnose", lambda: called.append(True), next_stage="REVIEWING")
    assert called == []
    assert ctx.step == 0


def test_timeout_returns_without_waiting_for_handler(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s11")
    old = wf.actions["diagnose"]["timeout_seconds"]
    wf.actions["diagnose"]["timeout_seconds"] = 0.02
    started = time.perf_counter()
    try:
        with pytest.raises(HarnessViolation):
            h.execute(ctx, "interviewer", "diagnose", lambda: time.sleep(0.30))
    finally:
        wf.actions["diagnose"]["timeout_seconds"] = old
    assert time.perf_counter() - started < 0.15


def test_followup_resets_for_new_main_question(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s12", stage="SCORING")
    h.execute(ctx, "interviewer", "followup", lambda: {})
    h.execute(ctx, "interviewer", "followup", lambda: {})
    assert ctx.followup_count == 2
    h.transition(ctx, "ASKING")
    assert ctx.followup_count == 0


def test_decision_requires_reason_code_and_exact_version(tmp_path):
    class FakeClient:
        model = "fake"
        def __init__(self, payload): self.payload = payload
        def chat(self, messages, **kwargs):
            from agent_runtime.zhipu_client import LLMResponse
            return LLMResponse(json.dumps(self.payload), "fake")

    with pytest.raises(DecisionError):
        Orchestrator(ROOT / "core" / "workflow.yaml", "s13", client=FakeClient({
            "agent": "interviewer", "action": "diagnose", "session_version": 0
        })).decide("完成诊断", {})

    with pytest.raises(DecisionError):
        Orchestrator(ROOT / "core" / "workflow.yaml", "s14", client=FakeClient({
            "agent": "interviewer", "action": "diagnose", "session_version": 1, "reason_code": "ok"
        })).decide("完成诊断", {})


def test_decision_rejects_unauthorized_tool(tmp_path):
    class FakeClient:
        model = "fake"
        def chat(self, messages, **kwargs):
            from agent_runtime.zhipu_client import LLMResponse
            return LLMResponse(json.dumps({
                "agent": "interviewer", "action": "diagnose", "session_version": 0,
                "reason_code": "ok", "tool": "memory_search"
            }), "fake")
    with pytest.raises(DecisionError):
        Orchestrator(ROOT / "core" / "workflow.yaml", "s15", client=FakeClient()).decide("完成诊断", {})


def test_trace_redacts_sensitive_text(tmp_path):
    tracer = TraceRecorder(tmp_path / "trace")
    tracer.record({"event": "x", "observations": {"resume": "SECRET-RESUME"}}, "../unsafe session")
    path = next((tmp_path / "trace").glob("*.jsonl"))
    raw = path.read_text(encoding="utf-8")
    assert "SECRET-RESUME" not in raw
    assert "sha256" in raw



def test_review_schema_accepts_report_text(tmp_path):
    wf, h = make_harness(tmp_path)
    ctx = HarnessContext("s16", stage="REVIEWING")
    result = h.execute(ctx, "reviewer", "review", lambda: "# report", next_stage="FINISHED")
    assert result == "# report"
    assert ctx.stage == "FINISHED"

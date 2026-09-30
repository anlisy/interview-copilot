import json

from stage4.memory.memory_store import MemoryStore
from stage8.decision_router import OnlineDecisionRouter
from stage8.runtime import OnlineInterviewRuntime
from stage8.session_store import FileSessionStateStore
from stage8.text_runner import EchoTextRunner
from stage8.trace import OnlineTraceRecorder
from stage6.decision.rule import RuleDecisionEngine
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "test_support" / "skills"


def test_online_runtime_closes_into_raw_trajectory(tmp_path):
    root = tmp_path / "memory"
    runtime = OnlineInterviewRuntime(
        memory=MemoryStore(root),
        skills_root=SKILLS,
        decision_router=OnlineDecisionRouter(RuleDecisionEngine()),
        text_runner=EchoTextRunner(),
        session_store=FileSessionStateStore(tmp_path / "sessions"),
        trace=OnlineTraceRecorder(tmp_path / "trace"),
        stage7_mode="rule",
    )
    result = runtime.run_turn(session_id="s1", task="根据 Redis 项目设计项目深挖面试题", agent="interviewer", action="generate")
    assert result.agent_output.engine == "echo"
    assert result.state.turn_count == 1
    rows = MemoryStore(root).raw.read("s1")
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"
    trace_files = list((tmp_path / "trace").glob("*.jsonl"))
    assert trace_files
    payload = json.loads(trace_files[0].read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "online_turn"
    assert "task_hash" in payload


def test_second_turn_runs_intent_judge(tmp_path):
    runtime = OnlineInterviewRuntime(
        memory=MemoryStore(tmp_path / "memory"),
        skills_root=SKILLS,
        decision_router=OnlineDecisionRouter(RuleDecisionEngine()),
        text_runner=EchoTextRunner(),
        session_store=FileSessionStateStore(tmp_path / "sessions"),
        trace=OnlineTraceRecorder(tmp_path / "trace"),
        stage7_mode="rule",
    )
    runtime.run_turn(session_id="s2", task="解释 Redis 缓存击穿", action="generate")
    second = runtime.run_turn(session_id="s2", task="Redis 缓存击穿怎么治理", action="followup")
    assert second.intent is not None
    assert second.intent.kind == "intent"


def test_finish_session_consolidates_existing_candidate(tmp_path):
    root = tmp_path / "memory"
    memory = MemoryStore(root)
    memory.capture_turn(
        "s3",
        "user",
        "我负责过 Redis 缓存治理并解决缓存击穿。",
        metadata={
            "memory_candidate": True,
            "memory_type": "verified_experience",
            "confidence": 0.95,
            "importance": 0.9,
        },
    )
    runtime = OnlineInterviewRuntime(
        memory=memory,
        skills_root=SKILLS,
        decision_router=OnlineDecisionRouter(RuleDecisionEngine()),
        text_runner=EchoTextRunner(),
        session_store=FileSessionStateStore(tmp_path / "sessions"),
        trace=OnlineTraceRecorder(tmp_path / "trace"),
        stage7_mode="rule",
    )
    result = runtime.finish_session("s3")
    assert result["status"] == "committed"
    assert len(result["committed_record_ids"]) == 1

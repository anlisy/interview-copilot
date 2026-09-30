import sys
import types

from stage4.memory.memory_store import MemoryStore
from stage6.decision.rule import RuleDecisionEngine
from stage8.decision_router import OnlineDecisionRouter
from stage8.memory_capture import OnlineMemoryCapture
from stage8.runtime import OnlineInterviewRuntime
from stage8.session_store import FileSessionStateStore
from stage8.stage1_agent_runner import Stage1AgentRunner, Stage1ContextInjector
from stage8.text_runner import EchoTextRunner
from stage8.trace import OnlineTraceRecorder

from pathlib import Path
SKILLS = Path(__file__).resolve().parents[1] / "test_support" / "skills"


def make_runtime(tmp_path, *, agent_runner=None):
    return OnlineInterviewRuntime(
        memory=MemoryStore(tmp_path / "memory"),
        skills_root=SKILLS,
        decision_router=OnlineDecisionRouter(RuleDecisionEngine()),
        text_runner=EchoTextRunner(),
        agent_runner=agent_runner,
        session_store=FileSessionStateStore(tmp_path / "sessions"),
        trace=OnlineTraceRecorder(tmp_path / "trace"),
        stage7_mode="rule",
    )


def test_state_bridge_tracks_stage1_lifecycle(tmp_path):
    class Agent:
        def generate(self, resume, jd, total, type_ratio):
            return [{"question": "Q1"}]

    runner = Stage1AgentRunner({"interviewer": Agent})
    runtime = make_runtime(tmp_path, agent_runner=runner)
    result = runtime.run_turn(
        session_id="s1",
        task="生成面试题",
        agent="interviewer",
        action="generate",
        resume="候选人有 Redis 经验",
        jd="Java 后端岗位",
        total=1,
    )
    assert result.state.workflow_stage == "ASKING"
    history = result.state.metadata["state_history"]
    assert [(x["source"], x["target"]) for x in history] == [("INIT", "GENERATING"), ("GENERATING", "ASKING")]


def test_stage1_runner_really_injects_context_into_legacy_prompt_loader(monkeypatch):
    fake_tools = types.ModuleType("tools")
    fake_q = types.ModuleType("tools.question_tools")
    fake_q._load_prompt = lambda name: "BASE {resume} {jd}"
    fake_tools.question_tools = fake_q
    monkeypatch.setitem(sys.modules, "tools", fake_tools)
    monkeypatch.setitem(sys.modules, "tools.question_tools", fake_q)

    class Agent:
        def generate(self, resume, jd, total, type_ratio):
            import tools.question_tools as q
            prompt = q._load_prompt("interviewer.txt").format(resume=resume, jd=jd)
            return [{"prompt_seen": prompt}]

    runner = Stage1AgentRunner({"interviewer": Agent})
    out = runner.run(
        "MEMORY: 候选人做过 Redis 缓存击穿治理",
        agent="interviewer",
        action="generate",
        request={"resume": "R", "jd": "J", "total": 1, "type_ratio": {"project": 1.0}},
    )
    assert "MEMORY: 候选人做过 Redis 缓存击穿治理" in out.text
    assert out.metadata["context_injected"] is True


def test_online_answer_becomes_memory_candidate_and_finish_consolidates(tmp_path):
    runtime = make_runtime(tmp_path)
    answer = "我负责过 Redis 缓存治理，解决过缓存击穿，线上通过限流和缓存保护降低风险。"
    result = runtime.run_turn(
        session_id="memory-session",
        task="请介绍一个你做过的缓存治理项目",
        action="generate",
        answer=answer,
        memory_candidate=True,
        memory_confidence=0.95,
        memory_importance=0.9,
    )
    capture = result.state.metadata["last_memory_capture"]
    assert capture["candidate"] is True
    rows = MemoryStore(tmp_path / "memory").raw.read("memory-session")
    assert any((r.get("extra") or {}).get("memory_candidate") is True for r in rows)

    consolidated = runtime.finish_session("memory-session")
    assert consolidated["status"] == "committed"
    assert len(consolidated["committed_record_ids"]) == 1
    assert FileSessionStateStore(tmp_path / "sessions").load_state("memory-session").workflow_stage == "FINISHED"


def test_memory_capture_auto_detection_is_conservative():
    cap = OnlineMemoryCapture()
    positive = cap.classify("我负责过 Redis 缓存治理，解决过缓存击穿问题。")
    negative = cap.classify("请给我介绍一下 Redis 缓存击穿原理。")
    assert positive.candidate is True
    assert negative.candidate is False


def test_finished_finish_is_idempotent_and_does_not_increment_turn(tmp_path):
    runtime = make_runtime(tmp_path)
    answer = "我负责过 Redis 缓存治理，解决过缓存击穿。"
    first = runtime.run_turn(
        session_id="finished-session",
        task="介绍一个 Redis 项目",
        action="generate",
        answer=answer,
        memory_candidate=True,
    )
    finish = runtime.finish_session("finished-session")
    state1 = FileSessionStateStore(tmp_path / "sessions").load_state("finished-session")
    before = state1.turn_count
    second = runtime.run_turn(
        session_id="finished-session",
        task="结束本轮面试",
        action="review",
        finish=True,
    )
    assert second.state.workflow_stage == "FINISHED"
    assert second.state.turn_count == before
    assert second.agent_output.metadata["idempotent_finish"] is True
    assert second.consolidation == finish


def test_explicit_agent_action_wins_over_conflicting_skill_decision(tmp_path):
    runtime = make_runtime(tmp_path)
    result = runtime.run_turn(
        session_id="contract-session",
        task="生成面试题",
        agent="interviewer",
        action="generate",
    )
    assert result.skill is not None
    assert result.state.last_skill == "question-design"
    assert result.skill.metadata["decision_action_mismatch"] is True
    assert result.skill.metadata["expected_skill"] == "question-design"
    assert result.skill.metadata["mismatch_policy"] == "explicit_agent_action_wins"


def test_route_result_exposes_clear_online_semantics():
    from stage6.decision.rule import RuleDecisionEngine
    from stage6.decision.schema import DecisionTask
    from stage8.decision_router import OnlineDecisionRouter
    router = OnlineDecisionRouter(RuleDecisionEngine())
    result = router.decide(
        DecisionTask("semantic", "skill", "生成面试题", {"question-design": "生成面试题", "interview-review": "复盘"}),
        kind="skill",
    )
    payload = result.to_dict()
    assert payload["decision_route"] == payload["route"]
    assert payload["fallback_applied"] == payload["fallback"]


def test_finished_session_rejects_new_non_finish_turn(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.run_turn(session_id="terminal-session", task="介绍一个 Redis 项目", action="generate")
    runtime.finish_session("terminal-session")
    try:
        runtime.run_turn(session_id="terminal-session", task="继续追问", action="followup")
    except RuntimeError as exc:
        assert "session already finished" in str(exc)
    else:
        raise AssertionError("terminal session accepted a new turn")

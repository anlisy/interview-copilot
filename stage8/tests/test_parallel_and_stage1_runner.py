from stage8.runtime import OnlineInterviewRuntime
from stage8.stage1_agent_runner import Stage1AgentRunner
from stage8.text_runner import EchoTextRunner
from stage8.decision_router import OnlineDecisionRouter
from stage4.memory.memory_store import MemoryStore
from stage4.memory.memory_store import MemoryStore
from stage6.decision.rule import RuleDecisionEngine
from stage8.session_store import FileSessionStateStore
from stage8.trace import OnlineTraceRecorder
import time


class FakeAgent:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def generate(self, resume, jd, total, type_ratio):
        self.calls += 1
        return [{"question": "Q", "total": total}]

    def score(self, q_type, question, answer):
        self.calls += 1
        return {"score": 4, "type": q_type}

    def review(self, position, qa_list):
        self.calls += 1
        return "reviewed"


def test_stage1_agent_runner_interviewer_adapter():
    created = {}
    def factory():
        a = FakeAgent("x")
        created["a"] = a
        return a
    runner = Stage1AgentRunner({"interviewer": factory})
    out = runner.run("ctx", task="generate", agent="interviewer", action="generate", request={"resume":"r", "jd":"j", "total":3, "type_ratio":{"project":1.0}})
    assert out.engine == "stage1-agent"
    assert '"total": 3' in out.text
    assert created["a"].calls == 1


def test_stage1_agent_runner_reuses_agent_instance():
    calls = []
    def factory():
        calls.append(1)
        return FakeAgent("x")
    runner = Stage1AgentRunner({"scorer": factory})
    runner.run("ctx", task="q", agent="scorer", action="generate", request={"question":"q", "answer":"a"})
    runner.run("ctx", task="q", agent="scorer", action="generate", request={"question":"q2", "answer":"a2"})
    assert len(calls) == 1

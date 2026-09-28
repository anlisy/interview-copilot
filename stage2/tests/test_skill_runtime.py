from pathlib import Path

import pytest

from stage2.agent_runtime.frontmatter import SkillFormatError, split_frontmatter, validate_frontmatter
from stage2.agent_runtime.skill_registry import SkillRegistry
from stage2.agent_runtime.skill_runtime import SkillRuntime
from stage2.agent_runtime.skill_selector import RuleSkillSelector


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def test_registry_discovers_six_interview_skills():
    registry = SkillRegistry(SKILLS)
    names = [x.name for x in registry.discover()]
    assert names == sorted(names)
    assert len(names) == 6
    assert set(names) == {
        "question-design",
        "question-followup",
        "question-intent",
        "answer-evaluation",
        "interview-review",
        "difficulty-control",
    }


def test_all_skills_validate():
    registry = SkillRegistry(SKILLS)
    assert registry.validate_all() == []


def test_skill_frontmatter_contract():
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
        assert validate_frontmatter(fm, skill_dir_name=path.parent.name) == []
        assert body.strip()
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500


def test_question_design_is_selected_for_question_generation():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("根据简历和JD设计项目深挖面试题，避免重复", limit=1)[0]
    assert top.skill.name == "question-design"
    assert top.score > 0


def test_followup_is_selected_for_answer_depth():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("根据候选人的回答深度继续追问，重点挖边界", limit=1)[0]
    assert top.skill.name == "question-followup"
    assert top.score > 0


def test_intent_is_selected_for_similar_question_classification():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("判断两个Redis问题是原理、原因还是方案，不能只看向量相似度", limit=1)[0]
    assert top.skill.name == "question-intent"
    assert top.score > 0


def test_answer_evaluation_is_selected_for_rubric_scoring():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("按照正确性、深度、推理、工程性、边界对回答评分", limit=1)[0]
    assert top.skill.name == "answer-evaluation"
    assert top.score > 0


def test_review_is_selected_for_session_review():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("生成整场面试复盘，找出薄弱环节和能力覆盖缺口", limit=1)[0]
    assert top.skill.name == "interview-review"
    assert top.score > 0


def test_difficulty_is_selected_for_calibration():
    runtime = SkillRuntime(SKILLS)
    top = runtime.resolve("根据候选人熟悉程度和上一题表现控制下一题难度", limit=1)[0]
    assert top.skill.name == "difficulty-control"
    assert top.score > 0


def test_context_intent_can_break_ties():
    runtime = SkillRuntime(SKILLS)
    candidates = runtime.resolve("面试问题评估", context={"intent": "评分"}, limit=3)
    assert candidates
    assert candidates[0].skill.name == "answer-evaluation"


def test_limit_is_respected():
    runtime = SkillRuntime(SKILLS)
    assert len(runtime.resolve("面试", limit=2)) == 2
    assert runtime.resolve("面试", limit=0) == []


def test_activation_uses_progressive_disclosure():
    runtime = SkillRuntime(SKILLS)
    metadata = runtime.discover()
    assert metadata
    activation = runtime.activate("question-followup")
    assert activation.metadata.name == "question-followup"
    assert "核心递进链" in activation.content
    assert activation.skill_dir == SKILLS / "question-followup"


def test_unknown_skill_cannot_be_activated():
    runtime = SkillRuntime(SKILLS)
    with pytest.raises(KeyError):
        runtime.activate("not-a-real-skill")


def test_resolve_and_activate_returns_same_skill():
    runtime = SkillRuntime(SKILLS)
    candidates, activation = runtime.resolve_and_activate("设计面试题并避免重复")
    assert candidates
    assert activation.metadata.name == candidates[0].skill.name


def test_skill_name_lookup_does_not_allow_path_traversal(tmp_path: Path):
    root = tmp_path / "skills"
    root.mkdir()
    skill = root / "safe-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: safe-skill\ndescription: safe skill\n---\n# 目标\nbody\n", encoding="utf-8"
    )
    runtime = SkillRuntime(root)
    with pytest.raises(KeyError):
        runtime.activate("../safe-skill")


def test_skill_descriptions_are_domain_specific():
    runtime = SkillRuntime(SKILLS)
    all_text = "\n".join(m.description for m in runtime.discover())
    assert "面试" in all_text
    assert "代码回归" not in all_text


def test_each_skill_has_required_operational_sections():
    required = ["# 目标", "## 适用场景", "## 输出", "## 失败处理"]
    for path in SKILLS.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        for section in required:
            assert section in text, f"{path} missing {section}"


def test_rule_selector_returns_margin_without_model_call():
    runtime = SkillRuntime(SKILLS)
    candidates = runtime.resolve("根据简历设计项目深挖面试题，避免重复", limit=3)
    selection = RuleSkillSelector().select(candidates)
    assert selection.selected.skill.name == "question-design"
    assert selection.margin >= 0
    assert selection.reason_code in {"clear_margin", "close_candidates"}


def test_all_skills_have_action_bindings():
    from stage2.agent_runtime.skill_bindings import get_skill_binding
    runtime = SkillRuntime(SKILLS)
    for meta in runtime.discover():
        binding = get_skill_binding(meta)
        assert binding.allowed_actions


def test_skill_metadata_allowed_actions_is_loaded():
    runtime = SkillRuntime(SKILLS)
    assert runtime.registry.read_metadata(SKILLS / "question-design").allowed_actions == ("generate",)


def test_managed_runtime_selects_skill_before_orchestrator():
    from stage2.agent_runtime.managed_runtime import ManagedRuntime

    class FakeContext:
        stage = "DIAGNOSIS"
        session_id = "managed-test"

    class FakeTracer:
        def __init__(self): self.events = []
        def record(self, event, session_id): self.events.append((event, session_id))

    class FakeHarness:
        def __init__(self): self.tracer = FakeTracer()

    class FakeWorkflow:
        def stage(self, name):
            return {"allowed_actions": ["generate"]}

    class FakeOrchestrator:
        def __init__(self):
            self.context = FakeContext()
            self.harness = FakeHarness()
            self.workflow = FakeWorkflow()
        def decide(self, goal, observations):
            assert observations["skill"]["name"] == "question-design"
            assert "# 目标" in observations["skill"]["instructions"]
            return {"agent": "interviewer", "action": "generate", "session_version": 0, "reason_code": "skill_guided"}
        def run(self, decision, handlers, **kwargs):
            return handlers[decision["action"]]()

    runtime = ManagedRuntime(FakeOrchestrator(), str(SKILLS))
    managed, decision = runtime.decide("根据简历设计项目深挖面试题", {})
    assert managed.activation.metadata.name == "question-design"
    assert decision["action"] == "generate"
    assert runtime.run(managed, decision, {"generate": lambda: ["ok"]}) == ["ok"]




def test_managed_runtime_does_not_enforce_skill_at_prerequisite_stage():
    from stage2.agent_runtime.managed_runtime import ManagedRuntime

    class FakeContext:
        stage = "INIT"
        session_id = "managed-prereq"

    class FakeTracer:
        def record(self, *args, **kwargs): pass

    class FakeHarness:
        tracer = FakeTracer()

    class FakeWorkflow: 
        def stage(self, name):
            return {"allowed_actions": ["diagnose"]}

    class FakeOrchestrator:
        context = FakeContext()
        harness = FakeHarness()
        workflow = FakeWorkflow()
        def decide(self, goal, observations):
            assert "skill" not in observations
            return {"agent": "interviewer", "action": "diagnose", "session_version": 0, "reason_code": "prerequisite"}

    runtime = ManagedRuntime(FakeOrchestrator(), str(SKILLS))
    managed, decision = runtime.decide("根据简历设计项目深挖面试题", {})
    assert managed is None
    assert decision["action"] == "diagnose"


def test_managed_runtime_enforces_skill_only_when_skill_action_is_available():
    from stage2.agent_runtime.managed_runtime import ManagedRuntime

    class FakeContext:
        stage = "DIAGNOSIS"
        session_id = "managed-skill-stage"

    class FakeTracer:
        def record(self, *args, **kwargs): pass

    class FakeHarness:
        tracer = FakeTracer()

    class FakeWorkflow:
        def stage(self, name):
            return {"allowed_actions": ["generate"]}

    class FakeOrchestrator:
        context = FakeContext()
        harness = FakeHarness()
        workflow = FakeWorkflow()
        def decide(self, goal, observations):
            assert observations["skill"]["name"] == "question-design"
            return {"agent": "interviewer", "action": "generate", "session_version": 0, "reason_code": "skill_guided"}

    runtime = ManagedRuntime(FakeOrchestrator(), str(SKILLS))
    managed, decision = runtime.decide("根据简历设计项目深挖面试题", {})
    assert managed is not None
    assert managed.activation.metadata.name == "question-design"
    assert decision["action"] == "generate"


def test_managed_runtime_rejects_action_outside_skill_contract():
    from stage2.agent_runtime.managed_runtime import ManagedRuntime, SkillActionMismatch

    class FakeContext:
        stage = "DIAGNOSIS"
        session_id = "managed-mismatch"

    class FakeTracer:
        def record(self, *args, **kwargs): pass

    class FakeHarness:
        tracer = FakeTracer()

    class FakeWorkflow:
        def stage(self, name):
            return {"allowed_actions": ["generate"]}

    class FakeOrchestrator:
        context = FakeContext()
        harness = FakeHarness()
        workflow = FakeWorkflow()
        def decide(self, goal, observations):
            return {"agent": "scorer", "action": "score", "session_version": 0, "reason_code": "bad"}

    runtime = ManagedRuntime(FakeOrchestrator(), str(SKILLS))
    with pytest.raises(SkillActionMismatch):
        runtime.decide("根据简历设计项目深挖面试题", {})


def test_managed_runtime_integrates_with_stage1_orchestrator(tmp_path):
    from stage1.agent_runtime.orchestrator import Orchestrator
    from stage1.agent_runtime.trace import TraceRecorder
    from stage1.agent_runtime.zhipu_client import LLMResponse
    from stage2.agent_runtime.managed_runtime import ManagedRuntime

    stage1_root = Path(__file__).resolve().parents[2] / "stage1"

    class FakeClient:
        model = "fake"
        def chat(self, messages, **kwargs):
            return LLMResponse(
                '{"agent":"interviewer","action":"generate","session_version":0,"reason_code":"skill_guided"}',
                "fake",
            )

    trace_root = tmp_path / "trace"
    orchestrator = Orchestrator(
        stage1_root / "core" / "workflow.yaml",
        "stage2-integration",
        tracer=TraceRecorder(trace_root),
        client=FakeClient(),
    )
    orchestrator.context.stage = "DIAGNOSIS"
    runtime = ManagedRuntime(orchestrator, str(SKILLS))
    managed, decision = runtime.decide("根据简历和JD设计项目深挖面试题", {})
    assert managed.activation.metadata.name == "question-design"
    assert decision["action"] == "generate"
    result = runtime.run(managed, decision, {"generate": lambda: []}, next_stage="ASKING")
    assert result == []
    assert orchestrator.context.stage == "ASKING"
    trace = (trace_root / "stage2-integration.jsonl").read_text(encoding="utf-8")
    assert "skill_selected" in trace
    assert "before_action" in trace


def test_selector_rejects_unrelated_zero_evidence_task():
    from stage2.agent_runtime.skill_selector import NoSkillMatch
    runtime = SkillRuntime(SKILLS)
    candidates = runtime.resolve("今天天气怎么样", limit=3)
    with pytest.raises(NoSkillMatch):
        RuleSkillSelector().select(candidates)


def test_selector_marks_single_candidate_explicitly():
    runtime = SkillRuntime(SKILLS)
    candidates = runtime.resolve("按照正确性、深度、推理、工程性、边界对回答评分", limit=1)
    selection = RuleSkillSelector().select(candidates)
    assert selection.reason_code == "single_candidate"


def test_registry_rejects_binding_drift(tmp_path: Path):
    root = tmp_path / "skills"
    skill = root / "question-design"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: question-design\n"
        "description: 根据简历设计面试题\n"
        "metadata:\n"
        "  allowed_actions: [score]\n"
        "---\n"
        "# 目标\nbody\n\n## 适用场景\na\n\n## 输出\nb\n\n## 失败处理\nc\n",
        encoding="utf-8",
    )
    errors = SkillRegistry(root).validate_all()
    assert any("binding 不一致" in x for x in errors)


def test_registry_accepts_current_skill_contracts():
    assert SkillRegistry(SKILLS).validate_all() == []


def test_managed_runtime_falls_back_without_fabricating_a_skill():
    from stage2.agent_runtime.managed_runtime import ManagedRuntime

    class FakeContext:
        stage = "DIAGNOSIS"
        session_id = "managed-fallback"

    class FakeTracer:
        def __init__(self): self.events = []
        def record(self, event, session_id): self.events.append((event, session_id))

    class FakeHarness:
        def __init__(self): self.tracer = FakeTracer()

    class FakeWorkflow:
        def stage(self, name): return {"allowed_actions": ["generate"]}

    class FakeOrchestrator:
        def __init__(self):
            self.context = FakeContext()
            self.harness = FakeHarness()
            self.workflow = FakeWorkflow()
        def decide(self, goal, observations):
            assert "skill" not in observations
            return {"agent": "interviewer", "action": "generate", "session_version": 0, "reason_code": "no_skill_fallback"}

    runtime = ManagedRuntime(FakeOrchestrator(), str(SKILLS))
    managed, decision = runtime.decide("今天天气怎么样", {})
    assert managed is None
    assert decision["action"] == "generate"
    assert decision["skill_status"] == "not_matched"
    assert any(event[0]["event"] == "skill_not_matched" for event in runtime.harness.tracer.events)

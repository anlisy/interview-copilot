from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from stage2.agent_runtime.skill_runtime import SkillRuntime
from stage3.agent_runtime.default_tools import build_default_registry
from stage3.agent_runtime.tool_executor import ToolExecutor
from stage3.agent_runtime.tool_models import ToolCallContext
from stage3.agent_runtime.tool_policy import ToolPolicy
from stage4.agent_runtime.memory_runtime import MemoryAwareRuntime
from stage4.memory.memory_store import MemoryStore
from stage6.decision.schema import DecisionTask
from stage7.memory.checkpoint import CheckpointStore
from stage7.memory.consolidator_b import VersionedMemoryConsolidator
from stage7.memory.extractor import RuleMemoryExtractor, ZhipuMemoryExtractor
from stage7.memory.versioning import MemoryVersionStore

from .decision_router import OnlineDecisionRouter
from .schema import AgentTextResult, OnlineTurnResult, RouteResult, SessionState
from .session_store import FileSessionStateStore
from .trace import OnlineTraceRecorder
from .state_bridge import StateBridge
from .memory_capture import OnlineMemoryCapture


class OnlineInterviewRuntime:
    """Stage8：把决策、Skill、Tool、Memory、Agent 输出和 Session Consolidation 串成闭环。"""

    def __init__(
        self,
        *,
        memory: MemoryStore,
        skills_root: str | Path,
        decision_router: OnlineDecisionRouter,
        text_runner: Any,
        agent_runner: Any | None = None,
        session_store: Any | None = None,
        tool_registry: Any | None = None,
        tool_policy: ToolPolicy | None = None,
        tool_executor: ToolExecutor | None = None,
        trace: OnlineTraceRecorder | None = None,
        stage7_root: str | Path | None = None,
        stage7_mode: str = "rule",
        decision_parallel: bool = True,
        state_bridge: StateBridge | None = None,
        memory_capture: OnlineMemoryCapture | None = None,
    ):
        self.memory = memory
        self.memory_runtime = MemoryAwareRuntime(memory)
        self.skills = SkillRuntime(skills_root)
        self.router = decision_router
        self.text_runner = text_runner
        self.agent_runner = agent_runner
        self.sessions = session_store or FileSessionStateStore()
        self.registry = tool_registry or build_default_registry()
        self.policy = tool_policy or ToolPolicy()
        self.executor = tool_executor or ToolExecutor(self.registry, self.policy)
        self.trace = trace or OnlineTraceRecorder()
        self.stage7_root = Path(stage7_root or memory.root)
        self.stage7_mode = stage7_mode
        self.decision_parallel = decision_parallel
        self.state_bridge = state_bridge or StateBridge()
        self.memory_capture = memory_capture or OnlineMemoryCapture()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _turn_id(session_id: str, count: int, task: str) -> str:
        return hashlib.sha256(f"{session_id}:{count}:{task}".encode("utf-8")).hexdigest()[:20]

    def _save_state(self, state: SessionState) -> None:
        state.updated_at = self._now()
        self.sessions.save_state(state)

    def _load_state(self, session_id: str) -> SessionState:
        return self.sessions.load_state(session_id)

    def _validate_skills(self) -> None:
        errors = self.skills.validate()
        if errors:
            raise ValueError("Skill 校验失败: " + "; ".join(errors))

    def _route_skill(self, task: str, state: SessionState) -> RouteResult | None:
        candidates = self.skills.resolve(task, context={"intent": state.last_intent} if state.last_intent else {})
        if not candidates:
            return None
        options = {c.skill.name: c.skill.description for c in candidates}
        decision = self.router.decide(
            DecisionTask(
                task_id=f"skill:{uuid4().hex[:12]}",
                task_type="skill",
                state=task,
                options=options,
                metadata={"candidate_count": len(candidates)},
            ),
            kind="skill",
            alternatives=tuple(c.skill.name for c in candidates[1:]),
        )
        return decision

    def _route_tool(self, task: str, *, agent: str, action: str, eval_mode: bool, session_id: str, trace_id: str) -> RouteResult | None:
        ctx = ToolCallContext(agent=agent, eval_mode=eval_mode, session_id=session_id, trace_id=trace_id, action=action)
        visible = self.policy.visible_tools(self.registry, ctx)
        options = {"none": "本轮任务不需要调用任何外部工具"}
        for name in visible:
            options[name] = self.registry.get(name).description
        if len(options) == 1:
            return None
        decision = self.router.decide(
            DecisionTask(
                task_id=f"tool:{uuid4().hex[:12]}",
                task_type="tool",
                state=task,
                options=options,
            ),
            kind="tool",
            alternatives=tuple(x for x in options if x not in {"none"}),
        )
        if decision.route == "fallback" and decision.choice != "none":
            # 低置信度时不自动执行不确定 Tool，安全落到 none。
            return RouteResult(**{**decision.__dict__, "choice": "none", "reason": decision.reason + "; low_confidence_tool_suppressed"})
        return decision

    def _judge_intent(self, previous: str, current: str) -> RouteResult | None:
        if not previous.strip():
            return None
        options = {
            "same_intent": "两个问题考察相同的底层面试意图",
            "different_intent": "两个问题考察不同的底层面试意图",
        }
        return self.router.decide(
            DecisionTask(
                task_id=f"intent:{uuid4().hex[:12]}",
                task_type="intent",
                state={"question_a": previous, "question_b": current},
                options=options,
            ),
            kind="intent",
        )

    def _capture_online_memory(
        self,
        *,
        session_id: str,
        turn_id: str,
        task: str,
        answer: str,
        action: str,
        explicit_candidate: bool,
        memory_type: str,
        confidence: float,
        importance: float,
    ) -> dict[str, Any] | None:
        content = (answer or "").strip()
        if not content and action in {"scorer", "followup"}:
            content = task.strip()
        if not content:
            return None
        decision = self.memory_capture.classify(
            content,
            explicit=explicit_candidate,
            memory_type=memory_type,
            confidence=confidence,
            importance=importance,
        )
        if not decision.candidate:
            return decision.to_dict()
        record = self.memory.capture_turn(
            session_id,
            "user",
            content,
            turn_id=turn_id,
            stage="ANSWER" if answer.strip() else action.upper(),
            metadata={
                "memory_capture": True,
                "memory_candidate": True,
                "memory_type": decision.memory_type,
                "confidence": decision.confidence,
                "importance": decision.importance,
                "capture_reasons": list(decision.reasons),
                "source_stage": "stage8",
            },
        )
        return decision.to_dict() | {"record_id": record.record_id}

    _ACTION_SKILL_CONTRACT = {
        ("interviewer", "generate"): "question-design",
        ("interviewer", "followup"): "question-followup",
        ("scorer", "score"): "answer-evaluation",
        ("scorer", "generate"): "answer-evaluation",
        ("reviewer", "review"): "interview-review",
    }

    @classmethod
    def _expected_skill(cls, agent: str, action: str) -> str | None:
        return cls._ACTION_SKILL_CONTRACT.get((agent, action))

    @staticmethod
    def _apply_skill_contract(state: SessionState, route: RouteResult | None, expected: str | None) -> str | None:
        if route is None or not expected:
            return route.choice if route else None
        if route.choice == expected:
            return expected
        meta = dict(route.metadata)
        meta.update({
            "decision_action_mismatch": True,
            "expected_skill": expected,
            "decision_skill": route.choice,
            "mismatch_policy": "explicit_agent_action_wins",
        })
        state.metadata["last_decision_action_mismatch"] = meta
        return expected

    def _cached_finished_result(self, state: SessionState, task: str, trace_id: str) -> OnlineTurnResult:
        cached = state.metadata.get("last_consolidation")
        agent_text = state.last_answer or "Session already finished"
        agent_result = AgentTextResult(
            text=agent_text,
            engine="cached",
            metadata={"idempotent_finish": True},
        )
        return OnlineTurnResult(
            session_id=state.session_id,
            turn_id=str(state.metadata.get("last_turn_id") or self._turn_id(state.session_id, state.turn_count, state.last_question or task)),
            task=task,
            state=state,
            skill=None,
            tool=None,
            intent=None,
            context_memories=[],
            agent_output=agent_result,
            trace_id=str(state.metadata.get("last_trace_id") or trace_id),
            consolidation=cached,
        )

    def run_turn(
        self,
        *,
        session_id: str,
        task: str,
        agent: str = "interviewer",
        action: str = "generate",
        eval_mode: bool = False,
        finish: bool = False,
        profile: str = "",
        workflow: str = "",
        recent_turns: str = "",
        evidence: str = "",
        resume: str = "",
        jd: str = "",
        question: str = "",
        answer: str = "",
        position: str = "",
        qa_list: list[dict[str, Any]] | None = None,
        total: int = 5,
        type_ratio: dict[str, float] | None = None,
        execute_tool: bool = False,
        tool_arguments: dict[str, Any] | None = None,
        memory_candidate: bool = False,
        memory_type: str = "verified_experience",
        memory_confidence: float = 0.8,
        memory_importance: float = 0.6,
    ) -> OnlineTurnResult:
        if not task.strip():
            raise ValueError("task cannot be empty")
        self._validate_skills()
        state = self._load_state(session_id)
        if state.workflow_stage == "FINISHED":
            # 终态请求必须幂等；普通新请求也不得绕过 FINISHED。
            if finish:
                return self._cached_finished_result(state, task, str(state.metadata.get("last_trace_id") or ""))
            raise RuntimeError(f"session already finished: {session_id}")
        trace_id = self.trace.new_trace_id()
        state.turn_count += 1
        turn_id = self._turn_id(session_id, state.turn_count, task)

        # 1) Decision Layer
        if self.decision_parallel:
            with ThreadPoolExecutor(max_workers=3, thread_name_prefix="stage8-decision") as pool:
                skill_future = pool.submit(self._route_skill, task, state)
                tool_future = pool.submit(
                    self._route_tool,
                    task,
                    agent=agent,
                    action=action,
                    eval_mode=eval_mode,
                    session_id=session_id,
                    trace_id=trace_id,
                )
                intent_future = (
                    pool.submit(self._judge_intent, state.last_question, task)
                    if action in {"generate", "followup"} and state.last_question.strip()
                    else None
                )
                skill_route = skill_future.result()
                tool_route = tool_future.result()
                intent_route = intent_future.result() if intent_future else None
        else:
            skill_route = self._route_skill(task, state)
            tool_route = self._route_tool(
                task,
                agent=agent,
                action=action,
                eval_mode=eval_mode,
                session_id=session_id,
                trace_id=trace_id,
            )
            intent_route = (
                self._judge_intent(state.last_question, task)
                if action in {"generate", "followup"} and state.last_question.strip()
                else None
            )

        skill_text = ""
        expected_skill = self._expected_skill(agent, action)
        if skill_route:
            effective_skill = self._apply_skill_contract(state, skill_route, expected_skill) or skill_route.choice
            if expected_skill and skill_route.choice != expected_skill:
                metadata = dict(skill_route.metadata)
                metadata.update({
                    "decision_action_mismatch": True,
                    "expected_skill": expected_skill,
                    "decision_skill": skill_route.choice,
                    "mismatch_policy": "explicit_agent_action_wins",
                })
                skill_route = RouteResult(**{**skill_route.__dict__, "metadata": metadata, "reason": skill_route.reason + "; decision_action_mismatch"})
            try:
                activation = self.skills.activate(effective_skill)
                skill_text = activation.content
                state.last_skill = effective_skill
            except Exception as exc:
                skill_route = RouteResult(**{**skill_route.__dict__, "reason": skill_route.reason + f"; skill_activation_error:{type(exc).__name__}"})
        if intent_route:
            state.last_intent = intent_route.choice
        if tool_route:
            state.last_tool = tool_route.choice

        # 2) State Bridge: Stage8 热状态与 Stage1 状态机同步。
        if self.agent_runner is not None:
            self.state_bridge.before_agent(state, agent=agent, action=action)
        else:
            self.state_bridge.before_generic(state, action=action)

        # 3) Context
        effective_resume = resume or profile
        effective_jd = jd or evidence
        context_bundle = self.memory_runtime.prepare_context(
            session_id,
            task,
            workflow=workflow or state.workflow_stage,
            skill=skill_text,
            profile=effective_resume,
            recent_turns=recent_turns,
            evidence=effective_jd,
        )

        tool_output = None
        if execute_tool and tool_route and tool_route.choice != "none":
            tool_output = self.executor.call(
                tool_route.choice,
                tool_arguments or {"query": task},
                ToolCallContext(
                    agent=agent,
                    eval_mode=eval_mode,
                    session_id=session_id,
                    trace_id=trace_id,
                    action=action,
                ),
            ).__dict__

        render_context = context_bundle.rendered + (
            f"\n## Tool 输出\n{json.dumps(tool_output, ensure_ascii=False, default=str)}" if tool_output else ""
        )
        # 4) Agent Execution
        if self.agent_runner is not None:
            result = self.agent_runner.run(
                render_context,
                skill=state.last_skill,
                tool=state.last_tool or "none",
                task=task,
                agent=agent,
                action=action,
                request={
                    "profile": effective_resume,
                    "resume": effective_resume,
                    "jd": effective_jd,
                    "question": question or task,
                    "answer": answer,
                    "position": position,
                    "qa_list": qa_list or [],
                    "total": total,
                    "type_ratio": type_ratio or {"basic": 0.2, "project": 0.5, "scenario": 0.3},
                },
            )
            self.state_bridge.after_agent(state, agent=agent, action=action, finish=finish)
        else:
            result = self.text_runner.run(
                render_context,
                skill=state.last_skill,
                tool=state.last_tool or "none",
                task=task,
            )
            self.state_bridge.after_generic(state, action=action, finish=finish)

        # 5) Raw Trajectory + online memory capture
        self.memory_runtime.record_turn(
            session_id,
            "user",
            task,
            turn_id=turn_id,
            stage=action.upper(),
            metadata={"memory_capture": True, "source_stage": "stage8", "memory_candidate": False},
        )
        capture = self._capture_online_memory(
            session_id=session_id,
            turn_id=turn_id,
            task=task,
            answer=answer,
            action=action,
            explicit_candidate=memory_candidate,
            memory_type=memory_type,
            confidence=memory_confidence,
            importance=memory_importance,
        )
        self.memory_runtime.record_turn(
            session_id,
            "assistant",
            result.text,
            turn_id=turn_id,
            stage=action.upper(),
            metadata={"memory_capture": False, "source_stage": "stage8"},
        )

        state.last_question = task
        state.last_answer = result.text
        if answer.strip():
            state.last_user_answer = answer
        state.recent_questions = [*state.recent_questions, task][-10:]
        state.metadata["last_memory_capture"] = capture
        state.metadata["last_trace_id"] = trace_id
        self._save_state(state)

        output = OnlineTurnResult(
            session_id=session_id,
            turn_id=turn_id,
            task=task,
            state=state,
            skill=skill_route,
            tool=tool_route,
            intent=intent_route,
            context_memories=context_bundle.memories,
            agent_output=result,
            trace_id=trace_id,
        )
        self.trace.record_turn(trace_id=trace_id, session_id=session_id, task=task, result=output.to_dict())

        if finish:
            output.consolidation = self.finish_session(session_id)
            state.metadata["last_consolidation"] = output.consolidation
            state.metadata["last_turn_id"] = turn_id
            self._save_state(state)
        else:
            state.metadata["last_turn_id"] = turn_id
            self._save_state(state)
        return output

    def execute_tool(self, *, session_id: str, agent: str, action: str, tool: str, arguments: dict[str, Any], eval_mode: bool = False) -> dict[str, Any]:
        trace_id = self.trace.new_trace_id()
        result = self.executor.call(
            tool,
            arguments,
            ToolCallContext(agent=agent, action=action, session_id=session_id, eval_mode=eval_mode, trace_id=trace_id),
        )
        return result.__dict__

    def finish_session(self, session_id: str) -> dict[str, Any]:
        state = self._load_state(session_id)
        cached = state.metadata.get("last_consolidation")
        if state.workflow_stage == "FINISHED" and cached is not None:
            return cached
        if state.workflow_stage != "FINISHED":
            # 不强制 Agent 执行，仅完成状态边界与持久化。
            current = self.state_bridge.restore(state)
            if current == "ASKING":
                self.state_bridge.transition(state, "SCORING", reason="finish_session scoring boundary")
                self.state_bridge.transition(state, "REVIEWING", reason="finish_session review boundary")
            if self.state_bridge.restore(state) == "REVIEWING":
                self.state_bridge.transition(state, "FINISHED", reason="finish_session complete")
            self._save_state(state)
        checkpoints = CheckpointStore(self.stage7_root / "checkpoints")
        versions = MemoryVersionStore(self.stage7_root / "versioned")
        consolidator = VersionedMemoryConsolidator(self.memory, checkpoints=checkpoints, versions=versions)
        extractor = RuleMemoryExtractor() if self.stage7_mode == "rule" else ZhipuMemoryExtractor()
        result = consolidator.consolidate(session_id, extractor).to_dict()
        state.metadata["last_consolidation"] = result
        self._save_state(state)
        return result

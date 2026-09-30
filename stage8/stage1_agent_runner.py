from __future__ import annotations

import importlib
import json
import threading
import time
from types import ModuleType
from typing import Any, Callable

from .schema import AgentTextResult


class Stage1ContextInjector:
    """在不修改旧 Stage1 Agent 接口的前提下，把 Stage8 Context 注入其原 Prompt。"""

    MODULES = {
        "interviewer": "tools.question_tools",
        "scorer": "tools.score_tools",
        "reviewer": "tools.review_tools",
    }
    _lock = threading.RLock()

    @classmethod
    def run_with_context(cls, agent: str, context: str, fn: Callable[[], Any]) -> Any:
        module_name = cls.MODULES.get(agent)
        if not module_name or not context.strip():
            return fn()
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            # 自定义测试 Agent / 精简环境不一定存在 Stage1 tools。
            return fn()
        loader = getattr(module, "_load_prompt", None)
        if not callable(loader):
            return fn()

        safe_context = context.replace("{", "{{").replace("}", "}}")

        def wrapped(name: str) -> str:
            base = loader(name)
            return (
                base
                + "\n\n【Stage8 受控上下文】\n"
                + safe_context
                + "\n【Stage8 受控上下文结束】\n"
            )

        with cls._lock:
            setattr(module, "_load_prompt", wrapped)
            try:
                return fn()
            finally:
                setattr(module, "_load_prompt", loader)


class Stage1AgentRunner:
    """把现有 Stage1 Interviewer/Scorer/Reviewer 适配到 Stage8。"""

    def __init__(self, factories: dict[str, Callable[[], Any]] | None = None):
        self.factories = factories or {}
        self._agents: dict[str, Any] = {}

    def _build(self, name: str) -> Any:
        if name in self._agents:
            return self._agents[name]
        factory = self.factories.get(name)
        if factory is None:
            if name == "interviewer":
                from agents.interviewer import InterviewerAgent
                factory = InterviewerAgent
            elif name == "scorer":
                from agents.scorer import ScorerAgent
                factory = ScorerAgent
            elif name == "reviewer":
                from agents.reviewer import ReviewerAgent
                factory = ReviewerAgent
            else:
                raise ValueError(f"unsupported stage1 agent={name}")
        self._agents[name] = factory()
        return self._agents[name]

    def run(
        self,
        context: str,
        *,
        skill: str = "",
        tool: str = "none",
        task: str = "",
        agent: str = "interviewer",
        action: str = "generate",
        request: dict[str, Any] | None = None,
    ) -> AgentTextResult:
        request = request or {}
        started = time.perf_counter()
        target = self._build(agent)

        def invoke() -> Any:
            if agent == "interviewer" and action == "generate":
                resume = str(request.get("resume") or request.get("profile") or "")
                jd = str(request.get("jd") or "")
                if not resume:
                    raise ValueError("stage1 interviewer generate requires --resume or profile")
                if not jd:
                    raise ValueError("stage1 interviewer generate requires --jd")
                total = int(request.get("total", 5))
                type_ratio = request.get("type_ratio") or {"basic": 0.2, "project": 0.5, "scenario": 0.3}
                return target.generate(resume, jd, total, type_ratio)
            if agent == "scorer":
                q_type = str(request.get("q_type") or "project")
                question = str(request.get("question") or task)
                answer = str(request.get("answer") or "")
                if not answer:
                    raise ValueError("stage1 scorer requires --answer")
                return target.score(q_type, question, answer)
            if agent == "reviewer" and action == "review":
                position = str(request.get("position") or "")
                raw_qa = request.get("qa_list") or []
                if isinstance(raw_qa, str):
                    raw_qa = json.loads(raw_qa)
                return target.review(position, list(raw_qa))
            raise ValueError(f"stage1 adapter does not support agent={agent}, action={action}")

        value = Stage1ContextInjector.run_with_context(agent, context, invoke)
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
        return AgentTextResult(
            text=text,
            engine="stage1-agent",
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            metadata={
                "agent": agent,
                "action": action,
                "adapter": "stage1",
                "context_injected": bool(context.strip()),
                "context_chars": len(context),
                "skill": skill,
                "tool": tool,
            },
        )

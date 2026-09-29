from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from stage4.agent_runtime.context_manager import ContextBudget, ContextManager, ContextSection
from stage4.memory.memory_store import MemoryStore
from stage4.memory.redis_store import RedisSessionStore


@dataclass
class ContextBundle:
    session_id: str
    query: str
    memories: list[dict[str, Any]]
    rendered: str


class MemoryAwareRuntime:
    """Stage4 接入层：把 Stage1-3 产生的当前任务接到分层记忆与受控 Context。"""

    def __init__(
        self,
        memory: MemoryStore,
        redis_store: RedisSessionStore | None = None,
        context_manager: ContextManager | None = None,
    ):
        self.memory = memory
        self.redis = redis_store
        self.context = context_manager or ContextManager(ContextBudget(total_tokens=16000, output_reserve=2000))

    def prepare_context(
        self,
        session_id: str,
        task: str,
        *,
        system: str = "你是面试 Agent，只使用当前任务允许的数据和工具。",
        workflow: str = "",
        skill: str = "",
        profile: str = "",
        working_memory: str = "",
        recent_turns: str = "",
        evidence: str = "",
        recall_limit: int = 5,
    ) -> ContextBundle:
        hits = self.memory.recall(task, limit=recall_limit)
        memory_text = "\n".join(
            f"[{h['memory_type']}] {h['content']}"
            for h in hits
        )
        if memory_text:
            working_memory = f"{working_memory}\n{memory_text}".strip()

        sections = [
            ContextSection("系统契约", system, 100, 20),
            ContextSection("工作流", workflow, 90),
            ContextSection("当前 Skill", skill, 80),
            ContextSection("候选人画像", profile, 70),
            ContextSection("工作记忆", working_memory, 75),
            ContextSection("最近对话", recent_turns, 80),
            ContextSection("检索证据", evidence, 50),
            ContextSection("当前任务", task, 100, 20),
        ]
        rendered = self.context.assemble(sections)
        return ContextBundle(session_id=session_id, query=task, memories=hits, rendered=rendered)

    def record_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        turn_id: str | None = None,
        stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.memory.capture_turn(session_id, role, content, turn_id=turn_id, stage=stage, metadata=metadata)
        if self.redis:
            self.redis.patch(session_id, {
                "last_role": role,
                "last_turn_id": turn_id,
                "last_stage": stage,
                "last_content_summary": (content or "")[:240],
            })

    def record_memory_candidate(self, session_id: str, content: str, **kwargs: Any) -> None:
        self.memory.capture_fact(session_id, content, **kwargs)

    def consolidate(self, session_id: str):
        return self.memory.consolidate(session_id)

    def run(
        self,
        task: str,
        session_id: str,
        agent_runner: Callable[[str], Any],
        **context_kwargs: Any,
    ) -> tuple[Any, ContextBundle]:
        bundle = self.prepare_context(session_id, task, **context_kwargs)
        self.record_turn(session_id, "user", task, stage="RUN", metadata={"memory_capture": True})
        result = agent_runner(bundle.rendered)
        result_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        self.record_turn(session_id, "assistant", result_text, stage="RUN", metadata={"memory_capture": False})
        return result, bundle

from __future__ import annotations

from typing import Any, Callable

from .consolidator import ConsolidationResult, MemoryConsolidator
from .extractor import MemoryExtractor


class SessionLifecycleHook:
    """生命周期 Hook：只在 Session 完成时触发沉淀，不在每个 token/step 上操作长期记忆。"""

    def __init__(self, consolidator: MemoryConsolidator, extractor_factory: Callable[[], MemoryExtractor]):
        self.consolidator = consolidator
        self.extractor_factory = extractor_factory

    def __call__(self, event: str, *, session_id: str, **_: Any) -> ConsolidationResult | None:
        if event != "session_finished":
            return None
        return self.consolidator.consolidate(session_id, self.extractor_factory())

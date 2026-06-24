"""Agent 基类：统一 model 注入、prompt 加载、独立上下文标识"""
from core.config import ROOT
from core.llm import get_model


class BaseAgent:
    """所有面试 Agent 的基类。

    关键设计：每个 Agent 实例持有自己的 model 与 name，
    上下文（messages）每次调用独立构造，不跨 Agent 共享 —— 实现上下文隔离。
    """

    name = "base"

    def __init__(self, model=None):
        # 每个 Agent 独立持有 model（L2-c 做模型路由时这里可按 name 选不同模型）
        self.model = model or get_model()

    def _load_prompt(self, filename: str) -> str:
        return (ROOT / "prompts" / filename).read_text(encoding="utf-8")

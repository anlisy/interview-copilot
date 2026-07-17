"""Agent 基类：统一 model 注入、prompt 加载、独立上下文标识。

L2-c：每个 Agent 按自己的 name 从路由表选模型（配置驱动），
出题用强模型、评分用快模型，平衡质量与成本。
"""
from core.config import ROOT, get_model_for_agent
from core.llm import get_model


class BaseAgent:
    name = "base"

    def __init__(self, model=None):
        # L2-c: 按 Agent 的 name 路由到对应模型
        model_id = get_model_for_agent(self.name)
        self.model_id = model_id            # 记录用了哪个模型，便于日志/调试
        self.model = model or get_model(model_id)

    def _load_prompt(self, filename: str) -> str:
        return (ROOT / "prompts" / filename).read_text(encoding="utf-8")

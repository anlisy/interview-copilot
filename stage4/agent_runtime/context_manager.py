from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .token_counter import TokenCounter, default_counter


@dataclass(frozen=True)
class ContextBudget:
    total_tokens: int = 16000
    output_reserve: int = 2000

    @property
    def input_tokens(self) -> int:
        return max(0, self.total_tokens - self.output_reserve)


@dataclass(frozen=True)
class ContextSection:
    name: str
    text: str
    priority: int
    min_tokens: int = 0


class ContextManager:
    """token-aware context packing，不按字符硬截断。"""

    def __init__(self, budget: ContextBudget | None = None, counter: TokenCounter | None = None):
        self.budget = budget or ContextBudget()
        self.counter = counter or default_counter()

    def assemble(self, sections: Iterable[ContextSection]) -> str:
        items = list(sections)
        # 优先级高的先占额度，保持同优先级输入顺序。
        ordered = sorted(enumerate(items), key=lambda pair: (-pair[1].priority, pair[0]))
        used = 0
        accepted: list[tuple[int, ContextSection, int]] = []
        budget = self.budget.input_tokens

        for _, section in ordered:
            text = section.text or ""
            block = f"## {section.name}\n{text.strip()}\n"
            tokens = self.counter.count(block)
            if not text.strip():
                continue
            if used + tokens <= budget:
                accepted.append((len(accepted), section, tokens))
                used += tokens
                continue
            if section.min_tokens <= 0 or used >= budget:
                continue
            # 尽量从段落末尾逐步收缩，直到满足预算。
            lines = text.splitlines()
            clipped = text
            while lines and self.counter.count(f"## {section.name}\n{clipped}\n") + used > budget:
                lines.pop()
                clipped = "\n".join(lines)
            if clipped.strip() and self.counter.count(f"## {section.name}\n{clipped}\n") >= section.min_tokens:
                block_tokens = self.counter.count(f"## {section.name}\n{clipped}\n")
                accepted.append((len(accepted), ContextSection(section.name, clipped, section.priority, section.min_tokens), block_tokens))
                used += block_tokens

        # 输出按照业务固定顺序，而不是优先级排序顺序。
        accepted.sort(key=lambda item: items.index(item[1]))
        return "\n".join(f"## {section.name}\n{section.text.strip()}" for _, section, _ in accepted)

    def assemble_legacy(
        self,
        system: str,
        workflow: str,
        skill: str,
        profile: str,
        working_memory: str,
        recent_turns: str,
        evidence: str,
    ) -> str:
        sections = [
            ContextSection("系统契约", system, 100, 50),
            ContextSection("工作流", workflow, 90, 20),
            ContextSection("当前 Skill", skill, 80, 20),
            ContextSection("候选人画像", profile, 70),
            ContextSection("工作记忆", working_memory, 60),
            ContextSection("最近对话", recent_turns, 80),
            ContextSection("检索证据", evidence, 50),
        ]
        return self.assemble(sections)

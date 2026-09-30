from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryCaptureDecision:
    candidate: bool
    memory_type: str = "verified_experience"
    confidence: float = 0.8
    importance: float = 0.6
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "reasons": list(self.reasons),
        }


class OnlineMemoryCapture:
    """在线回答候选记忆标记器。

    默认只把明显的第一人称项目经验写成 candidate，不把模型生成文本当作事实。
    """

    EXPERIENCE_MARKERS = (
        "我负责", "我做过", "我参与", "我设计", "我实现", "我优化",
        "我解决", "我排查", "我上线", "项目中", "曾经", "我们通过", "我们做了",
    )
    EVIDENCE_MARKERS = (
        "qps", "ms", "%", "万", "百万", "线上", "生产", "指标", "日志", "监控",
        "缓存击穿", "缓存穿透", "缓存雪崩", "限流", "降级", "分布式锁",
    )

    def classify(
        self,
        content: str,
        *,
        explicit: bool = False,
        memory_type: str = "verified_experience",
        confidence: float = 0.8,
        importance: float = 0.6,
    ) -> MemoryCaptureDecision:
        text = (content or "").strip()
        if explicit:
            return MemoryCaptureDecision(
                candidate=bool(text),
                memory_type=memory_type,
                confidence=max(0.0, min(confidence, 1.0)),
                importance=max(0.0, min(importance, 1.0)),
                reasons=("explicit",),
            )
        normalized = text.lower()
        experience = [m for m in self.EXPERIENCE_MARKERS if m in text]
        evidence = [m for m in self.EVIDENCE_MARKERS if m in normalized]
        candidate = len(text) >= 20 and bool(experience)
        if not candidate:
            return MemoryCaptureDecision(False, memory_type, confidence, importance)
        score = min(1.0, 0.72 + 0.05 * len(experience) + 0.03 * min(len(evidence), 5))
        imp = min(1.0, max(importance, 0.65 + 0.05 * min(len(evidence), 5)))
        reasons = tuple(["experience_marker", *(["evidence_marker"] if evidence else [])])
        return MemoryCaptureDecision(True, memory_type, round(score, 3), round(imp, 3), reasons)

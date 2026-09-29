from __future__ import annotations

from typing import Protocol


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class TiktokenCounter:
    """优先使用真实 tokenizer；编码可通过构造参数替换。"""

    def __init__(self, encoding_name: str = "cl100k_base"):
        import tiktoken
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text or "", disallowed_special=()))


class ConservativeCounter:
    """没有 tokenizer 依赖时的保守回退，仅用于本地开发，不冒充模型精确 token 数。"""

    def count(self, text: str) -> int:
        text = text or ""
        cjk = sum("\u4e00" <= ch <= "\u9fff" for ch in text)
        other = len(text) - cjk
        return cjk + max(0, (other + 3) // 4)


def default_counter() -> TokenCounter:
    try:
        return TiktokenCounter()
    except Exception:
        return ConservativeCounter()

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ZhipuAPIError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_id: str | None = None
    raw: dict[str, Any] | None = None


class ZhipuClient:
    """智谱 Chat Completions 最小封装，不依赖本地模型。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            raise ZhipuAPIError("缺少 ZHIPU_API_KEY")
        self.base_url = (base_url or os.getenv("ZHIPU_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = model or os.getenv("ZHIPU_MODEL", "glm-4-flash")
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        top_p: float = 0.7,
        max_tokens: int = 512,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        req = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ZhipuAPIError(f"智谱 API HTTP {exc.code}: {body[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise ZhipuAPIError(f"智谱 API 网络错误: {exc}") from exc

        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ZhipuAPIError(f"智谱 API 返回结构异常: {raw}") from exc
        usage = raw.get("usage") or {}
        return LLMResponse(
            content=str(content),
            model=str(raw.get("model", self.model)),
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            request_id=raw.get("request_id") or raw.get("id"),
            raw={**raw, "_latency_ms": round((time.perf_counter() - started) * 1000, 2)},
        )

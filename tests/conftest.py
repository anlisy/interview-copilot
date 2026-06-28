"""pytest 配置：禁用联网 + 强制 mock get_model，保证测试不调真实 LLM"""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_get_model(monkeypatch):
    """自动给所有测试 mock get_model，绝不真实初始化模型。"""
    fake = MagicMock(name="FakeModel")
    monkeypatch.setattr("core.llm.get_model", lambda *a, **k: fake)
    monkeypatch.setattr("agents.base.get_model", lambda *a, **k: fake)
    yield

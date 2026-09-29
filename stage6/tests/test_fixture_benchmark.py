from pathlib import Path

from stage6.benchmark.fixture import FixtureGLMEngine, FixtureJevEngine
from stage6.benchmark.runner import load_jsonl, run_benchmark
from stage6.decision.rule import RuleDecisionEngine


ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_fixture_has_three_engines():
    cases = load_jsonl(ROOT / "datasets" / "decision_benchmark.jsonl")
    report = run_benchmark({
        "rule": RuleDecisionEngine(),
        "glm": FixtureGLMEngine(error_ids={"intent-04"}),
        "jev": FixtureJevEngine(error_ids={"tool-04"}),
    }, cases)
    assert set(report) == {"rule", "glm", "jev"}
    for item in report.values():
        assert item["metrics"]["cases"] == 12
        overall = item["metrics"]["overall"]
        assert "accuracy" in overall
        assert "raw_accuracy" in overall
        assert "effective_accuracy" in overall
        assert "fallback_gain" in overall

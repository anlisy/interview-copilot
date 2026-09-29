import json
from pathlib import Path

from stage6.datasets.generate_formal_dataset import generate


def test_formal_dataset_generation(tmp_path: Path):
    spec = Path("stage6/datasets/decision_dataset_spec.json")
    manifest = generate(spec, tmp_path)
    assert manifest["counts"]["all"]["total"] == 110
    assert manifest["counts"]["all"]["task_type_counts"] == {"intent": 50, "skill": 30, "tool": 30}
    assert manifest["counts"]["validation"]["total"] == 55
    assert manifest["counts"]["test"]["total"] == 55


def test_formal_dataset_is_stratified(tmp_path: Path):
    spec = Path("stage6/datasets/decision_dataset_spec.json")
    manifest = generate(spec, tmp_path)
    for split in ("validation", "test"):
        by_task = manifest["counts"][split]["expected_counts_by_task"]
        assert set(by_task) == {"intent", "skill", "tool"}
        assert len(by_task["intent"]) == 2
        assert sum(by_task["intent"].values()) == 25
        assert len(by_task["skill"]) == 6
        assert sum(by_task["skill"].values()) == 15
        assert len(by_task["tool"]) == 4
        assert sum(by_task["tool"].values()) == 15


def test_intent_cases_have_two_questions(tmp_path: Path):
    spec = Path("stage6/datasets/decision_dataset_spec.json")
    generate(spec, tmp_path)
    rows = [json.loads(x) for x in (tmp_path / "decision_benchmark.jsonl").read_text(encoding="utf-8").splitlines()]
    intents = [r for r in rows if r["task_type"] == "intent"]
    assert len(intents) == 50
    assert all(r["state"]["question_a"] and r["state"]["question_b"] for r in intents)

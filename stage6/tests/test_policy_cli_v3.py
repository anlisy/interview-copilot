import json
from pathlib import Path

from stage6.benchmark import policy_cli


def test_write_and_load_frozen_policy(tmp_path: Path):
    dataset = tmp_path / "val.jsonl"
    dataset.write_text('{"id":"x","task_type":"skill","state":"a","options":{"a":"A"},"expected":"a"}\n', encoding="utf-8")
    frozen = tmp_path / "policy.json"
    calibration = {
        "cases": 1,
        "auto_accuracy": 1.0,
        "auto_coverage": 1.0,
        "min_auto_accuracy": 0.95,
        "min_auto_coverage": 0.6,
        "review_gap": 0.2,
    }
    policy = policy_cli.ThresholdPolicy(auto_threshold=0.9, review_threshold=0.7)
    policy_cli._write_frozen_policy(
        frozen,
        engine="jev",
        fallback_engine="glm",
        policy=policy,
        validation_dataset=dataset,
        calibration=calibration,
        thresholds=[0.5, 0.9],
    )
    loaded = policy_cli._load_frozen_policy(frozen)
    assert loaded.auto_threshold == 0.9
    assert loaded.review_threshold == 0.7
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    assert payload["selected_on"] == "validation"
    assert payload["dataset_sha256"]


def test_test_mode_requires_frozen_policy():
    import pytest
    from unittest.mock import patch

    argv = [
        "policy_cli",
        "--mode", "fixture",
        "--engine", "jev",
        "--test-dataset", "stage6/datasets/decision_benchmark.jsonl",
    ]
    with patch("sys.argv", argv):
        with pytest.raises(SystemExit):
            policy_cli.main()


def test_frozen_policy_rejects_threshold_outside_candidate_set(tmp_path: Path):
    frozen = tmp_path / "policy.json"
    frozen.write_text(json.dumps({
        "policy_type": "stage6_threshold_policy",
        "version": 2,
        "policy": {"auto_threshold": 0.19, "review_threshold": 0.0},
        "selection": {"threshold_candidates": [0.5, 0.6, 0.7]},
    }), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="not one of threshold_candidates"):
        policy_cli._load_frozen_policy(frozen)


def test_frozen_policy_roundtrip_persists_candidate_source(tmp_path: Path):
    dataset = tmp_path / "val.jsonl"
    dataset.write_text('{"id":"x","task_type":"skill","state":"a","options":{"a":"A"},"expected":"a"}\n', encoding="utf-8")
    frozen = tmp_path / "policy.json"
    calibration = {
        "cases": 1, "auto_accuracy": 1.0, "auto_coverage": 1.0,
        "min_auto_accuracy": 0.95, "min_auto_coverage": 0.6, "review_gap": 0.2,
    }
    policy_cli._write_frozen_policy(
        frozen, engine="jev", fallback_engine="glm",
        policy=policy_cli.ThresholdPolicy(0.7, 0.5),
        validation_dataset=dataset, calibration=calibration, thresholds=[0.5, 0.7, 0.9],
    )
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["selection"]["candidate_source"] == "actual_sweep"
    assert policy_cli._load_frozen_policy(frozen).auto_threshold == 0.7

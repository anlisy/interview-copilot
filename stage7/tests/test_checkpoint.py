from stage7.memory.checkpoint import CheckpointStore


def test_checkpoint_atomic_roundtrip(tmp_path):
    store = CheckpointStore(tmp_path)
    store.save("job/1", {"status": "resolved", "items": [1, 2]})
    assert store.load("job/1")["status"] == "resolved"
    store.clear("job/1")
    assert store.load("job/1") is None

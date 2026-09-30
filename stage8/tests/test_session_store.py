from stage8.schema import SessionState
from stage8.session_store import FileSessionStateStore


def test_file_session_state_roundtrip(tmp_path):
    store = FileSessionStateStore(tmp_path)
    state = SessionState(session_id="s1", turn_count=2, last_question="Q")
    store.save_state(state)
    loaded = store.load_state("s1")
    assert loaded.session_id == "s1"
    assert loaded.turn_count == 2
    assert loaded.last_question == "Q"

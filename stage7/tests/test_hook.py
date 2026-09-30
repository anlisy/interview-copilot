from stage7.memory.hooks import SessionLifecycleHook


class FakeService:
    def consolidate(self, session_id, extractor):
        return {"session_id": session_id, "extractor": type(extractor).__name__}


class FakeExtractor:
    pass


def test_hook_only_runs_on_session_finished():
    hook = SessionLifecycleHook(FakeService(), lambda: FakeExtractor())
    assert hook("step_finished", session_id="s1") is None
    assert hook("session_finished", session_id="s1") == {"session_id": "s1", "extractor": "FakeExtractor"}

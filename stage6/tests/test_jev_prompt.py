from stage6.decision.jev import JevDecisionEngine
from stage6.decision.schema import DecisionTask


class FakeClient:
    def __init__(self):
        self.last = None

    def system_one(self, *, state, questions, model):
        self.last = {"state": state, "questions": questions, "model": model}
        return {
            "answers": {
                "decision": {
                    "type": "choice",
                    "choice": "same_intent",
                    "probabilities": {"same_intent": 0.8, "different_intent": 0.2},
                    "confidence": 0.8,
                }
            },
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }


def test_jev_intent_prompt_is_english_and_receives_two_questions():
    client = FakeClient()
    engine = JevDecisionEngine(api_key="test", client=client, use_sdk=False)
    task = DecisionTask(
        "i1", "intent",
        {"question_a":"Redis 缓存击穿的原理是什么？", "question_b":"为什么 Redis 会发生缓存击穿？"},
        {
            "same_intent":"The two questions test the same underlying interview intent.",
            "different_intent":"The two questions test different underlying interview intents.",
        },
    )
    result = engine.decide(task)
    assert result.choice == "same_intent"
    instructions = client.last["questions"]["decision"]["instructions"]
    assert "question_a" in instructions or "underlying interview intent" in instructions
    assert "Determine whether" in instructions

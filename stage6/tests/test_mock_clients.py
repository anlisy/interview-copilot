from types import SimpleNamespace

from stage6.decision.zhipu import ZhipuDecisionEngine
from stage6.decision.jev import JevDecisionEngine
from stage6.decision.schema import DecisionTask


def test_zhipu_adapter_parses_structured_json_without_network():
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=4)
    message = SimpleNamespace(content='{"choice":"a","probabilities":{"a":0.8,"b":0.2},"confidence":0.8}')
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    engine = ZhipuDecisionEngine(client=client)
    result = engine.decide(DecisionTask("c1", "tool", "查本地资料", {"a":"本地知识库", "b":"外部面经"}))
    assert result.choice == "a"
    assert result.input_tokens == 12
    assert result.output_tokens == 4


def test_jev_adapter_parses_choice_response_without_network():
    answer = SimpleNamespace(choice="a", probabilities={"a":0.9,"b":0.1}, confidence=0.9)
    response = SimpleNamespace(choices={"decision": answer}, usage=SimpleNamespace(input_tokens=100, output_tokens=0))
    class FakeClient:
        def system_one(self, **kwargs):
            return response
    engine = JevDecisionEngine(client=FakeClient())
    result = engine.decide(DecisionTask("c2", "intent", {"question_a":"问题A", "question_b":"问题B"}, {"a":"同意图", "b":"不同意图"}))
    assert result.choice == "a"
    assert result.input_tokens == 100


def test_zhipu_adapter_derives_probabilities_when_model_omits_them():
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    message = SimpleNamespace(content='{"choice":"a","confidence":0.8}')
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    engine = ZhipuDecisionEngine(client=client)
    result = engine.decide(DecisionTask("c3", "tool", "查本地资料", {"a":"本地知识库", "b":"外部面经"}))
    assert abs(sum(result.probabilities.values()) - 1.0) < 1e-9
    assert result.probabilities["a"] == 0.8
    assert abs(result.probabilities["b"] - 0.2) < 1e-9
    assert result.metadata["probability_source"] == "derived_from_confidence"

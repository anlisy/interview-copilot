"""环境验证：跑通即说明 smolagents + 智谱 GLM 接通"""
from smolagents import ToolCallingAgent, tool
from core.llm import get_model


@tool
def add(a: int, b: int) -> int:
    """两数相加

    Args:
        a: 第一个数
        b: 第二个数
    """
    return a + b


if __name__ == "__main__":
    agent = ToolCallingAgent(tools=[add], model=get_model())
    result = agent.run("帮我算 123 + 456")
    print("结果:", result)

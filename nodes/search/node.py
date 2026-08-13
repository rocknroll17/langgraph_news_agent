"""search — planner 가 발행한 tool_call 들을 실행한다.

프리빌트 ToolNode 를 그대로 쓴다. for 문으로 직접 돌리면 직렬이라
검색 4건이 4배 느려진다. ToolNode 는 한 메시지의 tool_call 들을 동시에 처리한다.
"""

from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

NAME = "search"


def build(tools: list[BaseTool]) -> ToolNode:
    return ToolNode(tools)

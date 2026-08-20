"""follow_up — 1차 조사 결과를 보고 추가 검색을 발행한다."""

from langchain_core.messages import AIMessage

from config import FOLLOWUP_CALLS
from nodes.base import LLMNode
from state import State

from . import prompts


class FollowUpNode(LLMNode):
    name = "follow_up"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        response = self.chain.invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
            "max_calls": FOLLOWUP_CALLS,
        })
        response.tool_calls = response.tool_calls[:FOLLOWUP_CALLS]
        return {"messages": [response]}


def wants_more(state: State) -> bool:
    """추가 검색을 발행했는지. 조건부 엣지가 쓴다."""
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)

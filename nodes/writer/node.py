"""writer — 추린 사실만 보고 브리핑을 쓴다. 검색 원문은 보지 않는다."""

from nodes.base import LLMNode
from state import State

from . import prompts


class WriterNode(LLMNode):
    name = "writer"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        response = self.chain.invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
        })
        return {"messages": [response], "report": [response]}

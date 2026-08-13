"""synthesizer — 검색 원문에서 사실만 추린다.

원문(ToolMessage)을 보는 유일한 노드다. 이 뒤로는 추린 사실만 흐른다.
작은 모델에게 '원문 읽기'와 '글쓰기'를 동시에 시키지 않으려는 분리다.
"""

from nodes.base import LLMNode
from state import State

from . import prompts


class SynthesizerNode(LLMNode):
    name = "synthesizer"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        response = self.chain.invoke({
            "date": state["date"],
            "messages": state["messages"],
        })
        return {"messages": [response], "facts": str(response.content)}

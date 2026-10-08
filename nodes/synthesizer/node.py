"""synthesizer — 검색 원문에서 사실만 추린다.

원문(ToolMessage)을 보는 유일한 노드다. 이 뒤로는 추린 사실만 흐른다.
작은 모델에게 '원문 읽기'와 '글쓰기'를 동시에 시키지 않으려는 분리다.

2회차(follow_up 뒤)에는 1차 결과를 참조용으로만 받고, 이번 검색에서
새로 알아낸 것만 뽑는다. 1차 항목을 다시 쓰게 하면 출력이 길어지고
옮겨 적는 과정에서 수치가 틀어진다.
"""

from nodes.base import LLMNode
from state import State
from utils import articles, note

from . import prompts


class SynthesizerNode(LLMNode):
    name = "synthesizer"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        prior = state.get("facts", "")
        rounds = state.get("rounds", 0)
        consumed = state.get("consumed", 0)
        fresh = state["articles"][consumed:]        # 이번 회차분만

        try:
            response = self.chain.invoke({
                "date": state["date"],
                "articles": articles.render(fresh, start=consumed + 1),
                "prior": prompts.PRIOR.format(facts=prior) if prior else "",
            })
        except Exception as e:      # LLM 이 죽어도 이전 회차 사실은 살린다
            note("synthesizer", f"failed, keeping prior facts — {type(e).__name__}")
            return {
                "facts": prior,
                "rounds": rounds + 1,
                "consumed": len(state["articles"]),
            }

        new = str(response.content).strip()
        merged = f"{prior}\n\n{new}".strip() if prior else new
        return {
            "messages": [response],
            "facts": merged,
            "rounds": rounds + 1,
            "consumed": len(state["articles"]),
        }


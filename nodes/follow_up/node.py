"""follow_up — 1차 조사 결과를 보고 추가 검색을 발행한다.

"1차 검색어와 겹치지 말라"는 지시를 작은 모델이 자주 어긴다 — 실측에서 8개 전부를
그대로 다시 냈다. 무엇과 겹치면 안 되는지를 안 보여준 탓이 크다. 그래서 이미 던진
검색어를 프롬프트에 그대로 보여주고, 그래도 겹치면 코드가 걸러낸다.
걸러내고 남는 게 없으면 writer 로 간다.
"""

from langchain_core.messages import AIMessage

from config import FOLLOWUP_CALLS
from nodes.base import LLMNode
from state import State
from utils import note

from . import prompts


class FollowUpNode(LLMNode):
    name = "follow_up"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        asked = _asked(state)
        response = self.chain.invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
            "asked": "\n".join(f"- {q}" for q in asked),
            "max_calls": FOLLOWUP_CALLS,
        })
        fresh = [c for c in response.tool_calls if _key(c) not in asked]
        if dropped := len(response.tool_calls) - len(fresh):
            note("follow_up", f"dropped {dropped} repeated quer{'y' if dropped == 1 else 'ies'}")
        response.tool_calls = fresh[:FOLLOWUP_CALLS]
        return {"messages": [response]}


def _asked(state: State) -> list[str]:
    """지금까지 발행된 검색어. 순서를 지켜 프롬프트에 그대로 보여준다."""
    return list(dict.fromkeys(_key(c) for m in state["messages"]
                              if isinstance(m, AIMessage) for c in m.tool_calls))


def _key(call: dict) -> str:
    return " ".join(str(call["args"].get("query", "")).lower().split())


def wants_more(state: State) -> bool:
    """추가 검색을 발행했는지. 조건부 엣지가 쓴다."""
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)

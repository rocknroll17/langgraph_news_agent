"""planner — 검색 요청을 한 번에 여러 개 발행한다. 답은 쓰지 않는다."""

from langchain_core.messages import AIMessage

from config import MAX_CALLS, MIN_CALLS, PREV_DAYS
from nodes.base import LLMNode
from state import State
from utils import load_previous_reports

from . import prompts

REQUEST = (
    "오늘 미국 증시와 세계 시장의 변동, "
    "그리고 미국 정치 중 금융 관련 이슈를 조사해 브리핑하세요."
)


class PlannerNode(LLMNode):
    name = "planner"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        response = self.chain.invoke({
            "date": state["date"],
            "request": REQUEST,
            "min_calls": MIN_CALLS,
            "max_calls": MAX_CALLS,
            "user_input": _user_input(state["date"]),
        })
        # 상한은 코드로 강제한다. 프롬프트의 "최대 N회" 는 자주 무시된다.
        response.tool_calls = response.tool_calls[:MAX_CALLS]
        return {"messages": [response], "retry": state.get("retry", 0) + 1}


def enough_searches(state: State) -> bool:
    """검색을 충분히 발행했는지. 조건부 엣지가 쓴다."""
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and len(last.tool_calls) >= MIN_CALLS


def _user_input(date) -> str:
    """지난 브리핑을 참고 자료로 붙인다. 없으면 시작 신호만."""
    previous = load_previous_reports(date, PREV_DAYS)
    if not previous:
        return prompts.NO_PREV
    blocks = "\n\n".join(f"## {d} 브리핑\n{text}" for d, text in previous)
    return prompts.PREV_CONTEXT.format(previous=blocks)

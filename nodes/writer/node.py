"""writer — 사실 목록으로 뼈대를 잡고, 필요한 기사만 꺼내 읽어 글을 쓴다.

사실 목록만 주면 검색한 내용이 한 줄로 줄어들고, 기사를 통째로 주면
컨텍스트 한도에 걸린다. 그래서 목록만 보여주고 조회 도구를 쥐어준다.

조회 요청과 그 결과는 state["draft"] 에 쌓인다. messages 에는 앞 단계의
검색 원문 7만 자가 들어 있어 그대로 붙이면 컨텍스트가 넘친다.

상한(MAX_READ_ROUNDS)에 닿으면 tool_choice="none" 으로 바꾼다. 도구를 아예
빼면 "요청하라"는 지시만 남아 모델이 호출문을 텍스트로 적어버린다.
none 은 도구를 넘기되 서버가 디코딩 단계에서 호출을 막으므로 새지 않는다.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from config import MAX_READ_ROUNDS
from nodes.base import Node
from state import State

from . import prompts, tools


class WriterNode(Node):
    """LLMNode 를 쓰지 않는다. 회차마다 tool_choice 가 달라져
    template | model 을 미리 이어둘 수 없다."""

    name = "writer"

    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def run(self, state: State) -> dict:
        articles = state.get("articles") or []
        history = state.get("draft") or []

        done = _reads(history) >= MAX_READ_ROUNDS
        model = self.model.bind_tools(
            [tools.read_articles], tool_choice="none" if done else "auto"
        )

        draft = (prompts.TEMPLATE | model).invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
            "catalog": tools.catalog(articles),
            "max_reads": MAX_READ_ROUNDS,
            "draft": history,
        })

        if draft.tool_calls:
            n, total = _reads(history) + 1, MAX_READ_ROUNDS
            print(f"[writer] 기사 조회 {len(draft.tool_calls)}건 ({n}/{total}회차)")
            return {"draft": [draft]}

        return {"messages": [draft], "report": [draft]}


def wants_articles(state: State) -> bool:
    """조회를 요청했는지. 조건부 엣지가 쓴다."""
    last = (state.get("draft") or [None])[-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)


def _reads(history: list) -> int:
    """지금까지 조회를 요청한 횟수."""
    return sum(1 for m in history if getattr(m, "tool_calls", None))

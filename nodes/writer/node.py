"""writer — 사실 목록으로 뼈대를 잡고, 필요한 기사만 꺼내 읽어 글을 쓴다.

사실 목록만 주면 검색한 내용이 한 줄로 줄어들고, 기사를 통째로 주면
컨텍스트 한도에 걸린다. 그래서 목록만 보여주고 조회 도구를 쥐어준다.

조회 요청과 그 결과는 state["draft"] 에 쌓인다. messages 에는 앞 단계의
검색 원문 7만 자가 들어 있어 그대로 붙이면 컨텍스트가 넘친다.

상한에 닿으면 tool_choice="none" 으로 막는다. 도구를 아예 빼면
"요청하라"는 지시만 남아 모델이 호출문을 텍스트로 적어버린다.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from config import MAX_READ_ROUNDS
from nodes.base import Node
from state import State

from . import prompts, tools


class WriterNode(Node):
    name = "writer"

    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def run(self, state: State) -> dict:
        articles = state.get("articles") or []
        history = state.get("draft") or []

        messages = prompts.TEMPLATE.invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
            "catalog": tools.catalog(articles),
            "max_reads": MAX_READ_ROUNDS,
            "draft": history,
        }).to_messages()

        model = self.model.bind_tools(
            [tools.read_articles],
            tool_choice="none" if _reads(history) >= MAX_READ_ROUNDS else "auto",
        )
        draft = model.invoke(messages)

        if draft.tool_calls:
            return {"draft": [draft]}

        return {"messages": [draft], "report": [draft]}


def wants_articles(state: State) -> bool:
    """조회를 요청했는지. 조건부 엣지가 쓴다."""
    history = state.get("draft") or []
    return bool(history) and isinstance(history[-1], AIMessage) and bool(history[-1].tool_calls)


def _reads(history: list) -> int:
    """지금까지 조회를 요청한 횟수."""
    return sum(1 for m in history if getattr(m, "tool_calls", None))

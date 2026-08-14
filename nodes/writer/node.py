"""writer — 사실 목록으로 뼈대를 잡고, 필요한 기사만 꺼내 읽어 글을 쓴다.

사실 목록만 주면 검색한 내용이 한 줄로 줄어들고, 기사를 통째로 주면
컨텍스트 한도에 걸린다. 그래서 목록만 보여주고 조회 도구를 쥐어준다.

조회는 한 번만 허용한다. 왕복 한 번이 로컬 모델에서 20초 넘게 든다.
두 번째 호출에는 도구를 물리지 않아, 모델이 다시 조회할 수가 없다.
"""

from langchain_core.messages import AIMessage

from nodes.base import LLMNode
from state import State

from . import prompts, tools


class WriterNode(LLMNode):
    name = "writer"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        articles = state.get("articles") or []
        # 두 번째 호출에는 도구를 물리지 않는다. 조회를 반복할 수가 없다.
        model = self.model
        if not state.get("read_done"):
            model = model.bind_tools([tools.read_articles])

        draft = (self.template | model).invoke({
            "date": state["date"],
            "facts": state.get("facts", ""),
            "catalog": tools.catalog(articles),
        })

        if draft.tool_calls:
            print(f"[writer] 기사 조회 {len(draft.tool_calls)}건")
            return {"messages": [draft], "read_done": True}

        return {"messages": [draft], "report": [draft]}


def wants_articles(state: State) -> bool:
    """조회를 요청했는지. 조건부 엣지가 쓴다."""
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)

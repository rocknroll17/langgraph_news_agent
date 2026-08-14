"""그래프 조립과 실행.

이 파일에는 '무엇을 어떤 순서로' 만 둔다. '어떻게' 는 nodes/<이름>/ 안에 있다.

    planner ─(검색 충분)→ search → synthesizer → writer → checker → reviser → reporter → cleaner → END
       │ ▲
       │ └─(부족, 재시도 여유 있음)
       └───(하나도 못 얻음)────────→ synthesizer
"""

import os

from langgraph.graph import END, START, StateGraph

from config import MAX_RETRY, build_model, build_search_tool
from nodes import (
    SEARCH,
    CleanerNode,
    PlannerNode,
    ReporterNode,
    SynthesizerNode,
    CheckerNode,
    ReviserNode,
    WriterNode,
    build_search,
    enough_searches,
    search_count,
)
from state import State
from utils import PrettyTrace, today_kst


def route(state: State) -> str:
    """검색이 충분하면 진행, 부족하면 재시도, 재시도가 끝나면 있는 것만이라도 돌린다.

    하나도 못 얻었을 때만 검색을 건너뛴다. 그 경우 synthesizer 가 빈손으로
    받아 "확인되지 않음" 으로 처리한다.
    """
    if enough_searches(state):
        return SEARCH
    if state.get("retry", 0) < MAX_RETRY:
        return PlannerNode.name
    return SEARCH if search_count(state) else SynthesizerNode.name


def build_graph():
    model = build_model()
    tool = build_search_tool()

    nodes = [
        PlannerNode(model.bind_tools([tool])),
        SynthesizerNode(model),
        WriterNode(model),
        CheckerNode(model),
        ReviserNode(model),
        ReporterNode(),
        CleanerNode(),
    ]

    graph = StateGraph(State)
    graph.add_node(SEARCH, build_search([tool]))   # tool_call 들을 병렬 실행
    for node in nodes:
        graph.add_node(node.name, node)

    graph.add_edge(START, PlannerNode.name)
    graph.add_conditional_edges(
        PlannerNode.name, route, [SEARCH, PlannerNode.name, SynthesizerNode.name]
    )
    graph.add_edge(SEARCH, SynthesizerNode.name)
    graph.add_edge(SynthesizerNode.name, WriterNode.name)
    graph.add_edge(WriterNode.name, CheckerNode.name)
    graph.add_edge(CheckerNode.name, ReviserNode.name)
    graph.add_edge(ReviserNode.name, ReporterNode.name)
    graph.add_edge(ReporterNode.name, CleanerNode.name)
    graph.add_edge(CleanerNode.name, END)

    return graph.compile()


app = build_graph()


def initial_state() -> dict:
    """날짜는 그래프 밖에서 정한다. 노드 하나를 아낀다."""
    return {"messages": [], "retry": 0, "date": today_kst()}


if __name__ == "__main__":
    # TRACE=1     → 요약 (노드별로 무엇이 오갔는지)
    # TRACE=full  → 프롬프트·응답 전문
    trace = [PrettyTrace(full=os.environ.get("TRACE") == "full")] if os.environ.get("TRACE") else []
    app.invoke(initial_state(), config={"callbacks": trace})

"""그래프 조립과 실행.

이 파일에는 '무엇을 어떤 순서로' 만 둔다. '어떻게' 는 nodes/<이름>/ 안에 있다.

    planner → search → refiner(기사별 병렬) → synthesizer → follow_up
        → writer ⇄ read → checker → reviser(틀린 문장별 병렬) → assembler
        → reporter → cleaner → END

갈림길은 다섯이다.

    planner      검색이 부족하면 재시도, 끝내 하나도 못 얻으면 reporter 로 직행
    synthesizer  1회차면 follow_up 으로, 2회차면 writer 로
    follow_up    추가 검색을 냈으면 search 로 되돌아가고, 없으면 writer 로
    writer       기사 조회를 요청했으면 read 로, 아니면 checker 로
    checker      틀린 문장이 있으면 reviser 로 흩뿌리고, 없으면 바로 assembler 로
"""

import os

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config import MAX_RETRY, MAX_ROUNDS, build_model, build_search_tool
from nodes import (
    READ,
    SEARCH,
    AssemblerNode,
    CheckerNode,
    CleanerNode,
    FollowUpNode,
    PlannerNode,
    RefinerNode,
    ReporterNode,
    ReviserNode,
    SynthesizerNode,
    WriterNode,
    build_read,
    build_search,
    enough_searches,
    search_count,
    wants_articles,
    wants_more,
)
from state import State
from utils import Trace, articles, sentences, today_kst


def route(state: State) -> str:
    """검색이 충분하면 진행, 부족하면 재시도, 재시도가 끝나면 있는 것만이라도 돌린다.

    하나도 못 얻었으면 뒤 단계를 전부 건너뛰고 reporter 로 보낸다.
    근거 없이 LLM 을 네 번 더 돌려봐야 지어낸 글만 나온다.
    """
    if enough_searches(state):
        return SEARCH
    if state.get("retry", 0) < MAX_RETRY:
        return PlannerNode.name
    return SEARCH if search_count(state) else ReporterNode.name


def fan_out_refiners(state: State) -> list[Send]:
    """검색 결과를 기사 한 건씩 refiner 로 흩뿌린다.

    기사마다 독립이라 병렬로 돌 수 있다. 입력이 작아 빠르고,
    정리된 결과만 뒤로 넘어가 synthesizer·checker 가 가벼워진다.
    """
    payloads = articles.to_sends(state["messages"], state["date"])
    return [Send(RefinerNode.name, p) for p in payloads]


def route_after_synthesize(state: State) -> str:
    """1회차면 더 팔 게 있는지 물어보고, 2회차면 바로 글쓰기로 넘어간다."""
    return FollowUpNode.name if state.get("rounds", 0) < MAX_ROUNDS else WriterNode.name


def route_after_follow_up(state: State) -> str:
    """추가 검색을 냈으면 다시 검색, 아니면 있는 재료로 글을 쓴다."""
    return SEARCH if wants_more(state) else WriterNode.name


def route_after_write(state: State) -> str:
    """기사 조회를 요청했으면 꺼내주고, 아니면 검증으로 넘어간다."""
    return READ if wants_articles(state) else CheckerNode.name


def fan_out_revisers(state: State) -> list[Send] | str:
    """CONTRADICTED 문장을 하나씩 reviser 로 흩뿌린다. 없으면 바로 조립한다."""
    report = sentences.mark("\n".join(str(m.content) for m in state["report"]))
    wrong = [v for v in state.get("verdicts") or [] if v["verdict"] == "CONTRADICTED"]
    if not wrong:
        return AssemblerNode.name
    return [Send(ReviserNode.name, {
        "sentence": v["sentence"], "report": report,
        "correction": v["correction"], "evidence": v["evidence"],
    }) for v in wrong]


def build_graph(entry: str = PlannerNode.name, **compile_kwargs):
    """entry 는 개발용이다. 저장해 둔 상태로 중간 노드부터 이어 돌릴 때 쓴다."""
    model = build_model()
    tool = build_search_tool()

    nodes = [
        PlannerNode(model.bind_tools([tool])),
        RefinerNode(model),
        SynthesizerNode(model),
        FollowUpNode(model.bind_tools([tool])),
        WriterNode(model),
        CheckerNode(model),
        ReviserNode(model),
        AssemblerNode(),
        ReporterNode(),
        CleanerNode(),
    ]

    graph = StateGraph(State)
    graph.add_node(SEARCH, build_search([tool]))   # 검색 tool_call 병렬 실행
    graph.add_node(READ, build_read())            # 기사 조회 tool_call 실행
    for node in nodes:
        graph.add_node(node.name, node)

    # refiner·reviser 는 Send 로 흩뿌려서 들어가는 노드라 진입 간선이 조건부다.
    if entry == RefinerNode.name:
        graph.add_conditional_edges(START, fan_out_refiners, [RefinerNode.name])
    elif entry == ReviserNode.name:
        graph.add_conditional_edges(START, fan_out_revisers, [ReviserNode.name, AssemblerNode.name])
    else:
        graph.add_edge(START, entry)
    graph.add_conditional_edges(
        PlannerNode.name, route, [SEARCH, PlannerNode.name, ReporterNode.name]
    )
    graph.add_conditional_edges(SEARCH, fan_out_refiners, [RefinerNode.name])
    graph.add_edge(RefinerNode.name, SynthesizerNode.name)
    graph.add_conditional_edges(
        SynthesizerNode.name, route_after_synthesize, [FollowUpNode.name, WriterNode.name]
    )
    graph.add_conditional_edges(
        FollowUpNode.name, route_after_follow_up, [SEARCH, WriterNode.name]
    )
    graph.add_conditional_edges(WriterNode.name, route_after_write, [READ, CheckerNode.name])
    graph.add_edge(READ, WriterNode.name)
    graph.add_conditional_edges(
        CheckerNode.name, fan_out_revisers, [ReviserNode.name, AssemblerNode.name]
    )
    graph.add_edge(ReviserNode.name, AssemblerNode.name)
    graph.add_edge(AssemblerNode.name, ReporterNode.name)
    graph.add_edge(ReporterNode.name, CleanerNode.name)
    graph.add_edge(CleanerNode.name, END)

    return graph.compile(**compile_kwargs)


app = build_graph()


def initial_state() -> dict:
    """날짜는 그래프 밖에서 정한다. 노드 하나를 아낀다."""
    return {"messages": [], "retry": 0, "date": today_kst()}


if __name__ == "__main__":
    # TRACE=1 을 붙이면 노드별로 무엇이 오갔는지 찍는다
    trace = Trace() if os.environ.get("TRACE") else None
    result = app.invoke(initial_state(), config={"callbacks": [trace] if trace else []})
    if trace:
        trace.summary()
    raise SystemExit(1 if result.get("failed") else 0)   # CI 가 실패를 알아채도록

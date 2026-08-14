"""그래프 상태.

키마다 병합 규칙(리듀서)이 다르다.
- messages / report: add_messages 로 누적, 같은 ID 는 교체
- date: 새 값이 오면 갈아끼우고 없으면 유지
- 나머지: 리듀서 없음 = 덮어쓰기
"""

from datetime import date as Date
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph.message import add_messages


def keep_latest(left: Date | None, right: Date | None) -> Date | None:
    return right if right is not None else left


def collect(left: list | None, right: list | None) -> list:
    """기사를 모은다. None 을 주면 비운다 — cleaner 가 초기화할 때 쓴다."""
    if right is None:
        return []
    return (left or []) + right


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    report: Annotated[list[AIMessage], add_messages]   # writer 가 쓴 브리핑
    date: Annotated[Date, keep_latest]
    retry: int    # planner 재시도 횟수
    articles: Annotated[list[dict], collect]   # refiner 가 정리한 기사들 (회차 누적)
    facts: str    # synthesizer 가 추린 사실 목록 (회차별로 이어붙는다)
    rounds: int   # synthesizer 가 돈 횟수
    consumed: int # synthesizer 가 이미 읽은 articles 개수
    read_done: bool  # writer 가 기사 조회를 마쳤는지
    verdicts: list[dict]   # checker 의 주장별 판정
    cited: str             # reviser 가 수정·인용을 마친 본문
    failed: bool           # 브리핑을 만들지 못하고 끝났는지

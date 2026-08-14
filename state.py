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


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    report: Annotated[list[AIMessage], add_messages]   # writer 가 쓴 브리핑
    date: Annotated[Date, keep_latest]
    retry: int    # planner 재시도 횟수
    facts: str    # synthesizer 가 추린 사실 목록
    verdicts: list[dict]   # checker 의 주장별 판정
    cited: str             # reviser 가 수정·인용을 마친 본문
    failed: bool           # 브리핑을 만들지 못하고 끝났는지

"""writer 가 기사 원문을 꺼내 읽는 도구.

기사를 통째로 프롬프트에 넣으면 컨텍스트 한도(슬롯당 24,576 토큰)에 가까워진다.
목록만 보여주고 필요한 번호만 꺼내 쓰게 한다.

articles 는 InjectedState 로 받는다. 모델에게는 ids 만 보이고,
상태는 ToolNode 가 채워 넣는다.
"""

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, ToolNode

NAME = "read"
MAX_READS = 8   # 한 번에 꺼낼 수 있는 기사 수


@tool
def read_articles(
    ids: list[int],
    articles: Annotated[list[dict], InjectedState("articles")],
) -> str:
    """기사 목록에서 번호로 원문을 꺼낸다. 필요한 번호를 한 번에 넣을 것."""
    found = [articles[i - 1] for i in ids[:MAX_READS] if 1 <= i <= len(articles)]
    if not found:
        return "해당 번호의 기사가 없습니다."
    return "\n\n".join(f"{a['media']} | {a['title']}\n{a['content']}" for a in found)


def catalog(articles: list[dict]) -> str:
    """프롬프트에 넣을 기사 목록. 제목만 보여준다."""
    if not articles:
        return "(조회 가능한 기사 없음)"
    return "\n".join(f"[{i}] {a['media']} | {a['title']}" for i, a in enumerate(articles, 1))


def build() -> ToolNode:
    """조회 요청을 실행하는 노드."""
    return ToolNode([read_articles])

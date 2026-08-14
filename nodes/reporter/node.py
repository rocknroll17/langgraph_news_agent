"""reporter — 브리핑을 파일로 남기고 디스코드로 보낸다.

LLM 을 쓰지 않는 유일한 노드. 부수효과 담당이다.
"""

from langchain_core.messages import AIMessage

from nodes.base import Node
from state import State
from utils import discord, save_report, text

HEADER = "📈 **{date} 시장 브리핑**"
FAILED = "⚠️ **{date} 브리핑을 만들지 못했습니다**"


class ReporterNode(Node):
    name = "reporter"

    def run(self, state: State) -> dict:
        body = state.get("cited") or _join(state["report"])

        # 검색을 하나도 못 얻어 곧장 여기로 온 경우. 저장은 하지 않는다 —
        # 빈 브리핑이 reports/ 에 남으면 내일 planner 가 그걸 참고 자료로 읽는다.
        if not body.strip():
            discord.send(FAILED.format(date=state["date"]))
            print("[reporter] 브리핑 없음 — 실패 알림만 발송")
            return {"messages": [AIMessage(content="검색 실패로 브리핑을 건너뜀")], "failed": True}

        # 형식 문제는 프롬프트로 100% 막히지 않는다. 발행 직전에 코드가 한 번 더 건다.
        body = text.strip_markers(body)
        body, dropped = text.drop_empty_sections(body)
        if dropped:
            print(f"[reporter] 빈 섹션 제거: {', '.join(dropped)}")

        save_report(state["date"], body)   # 내일 planner 가 참고한다
        sent = discord.send(f"{HEADER.format(date=state['date'])}\n{body}")
        return {"messages": [AIMessage(content=f"디스코드 전송 완료 ({sent}건)")]}


def _join(messages) -> str:
    return "\n".join(str(m.content) for m in messages)

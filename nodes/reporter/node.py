"""reporter — 브리핑을 파일로 남기고 디스코드로 보낸다.

LLM 을 쓰지 않는 유일한 노드. 부수효과 담당이다.
"""

from langchain_core.messages import AIMessage

from nodes.base import Node
from state import State
from utils import discord, note, save_report, text

HEADER = "📈 **{date} 시장 브리핑**"
FAILED = "⚠️ **{date} 브리핑을 만들지 못했습니다**"


class ReporterNode(Node):
    name = "reporter"

    def run(self, state: State) -> dict:
        body = state.get("cited") or _join(state["report"])

        # 검색을 하나도 못 얻어 곧장 여기로 온 경우. 저장은 하지 않는다 —
        # 빈 브리핑이 reports/ 에 남으면 내일 planner 가 그걸 참고 자료로 읽는다.
        if not body.strip():
            note("reporter", "no briefing — sending failure notice only")
            discord.send(FAILED.format(date=state["date"]))
            return {"messages": [AIMessage(content="검색 실패로 브리핑을 건너뜀")], "failed": True}

        # 형식 문제는 프롬프트로 100% 막히지 않는다. 발행 직전에 코드가 한 번 더 건다.
        body = text.strip_markers(body)
        body, dropped = text.drop_empty_sections(body)
        path = save_report(state["date"], body)   # 내일 planner 가 참고한다
        sent = discord.send(f"{HEADER.format(date=state['date'])}\n{body}")

        # 발행은 되돌릴 수 없다. 무엇이 어디로 나갔는지 항상 남긴다.
        note("reporter",
             f"saved {path.name} ({len(body):,} chars)",
             *(f"dropped empty section: {d}" for d in dropped),
             f"sent {sent.messages} message(s) in {sent.chunks} chunk(s) "
             f"to {len(sent.targets)} webhook(s)",
             *(f"→ {t}" for t in sent.targets),
             *(f"failed {f}" for f in sent.failed))
        return {"messages": [AIMessage(content=f"디스코드 전송 완료 ({sent.messages}건)")]}


def _join(messages) -> str:
    return "\n".join(str(m.content) for m in messages)

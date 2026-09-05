"""reviser — CONTRADICTED 문장 하나를 올바른 값으로 고쳐 쓴다.

틀린 문장 수만큼 Send 로 띄워 병렬 실행한다. 각 인스턴스는 문장 하나만 고친다.
브리핑 전체를 다시 쓰게 하면 멀쩡한 문장이 바뀌고 새 환각이 들어온다.

본문 전체는 문맥으로만 보여준다 — 앞뒤의 "반면", "이에 따라" 와 방향(상승/하락)이
고친 값과 맞아야 한다. 그래도 출력은 표시된 문장 한 개뿐이다.
인용은 달지 않는다. 그건 assembler 가 번호로 붙인다.
"""

from typing_extensions import TypedDict

from nodes.base import LLMNode
from utils import note, sentences

from . import prompts


class ReviserInput(TypedDict):
    """Send 로 넘어오는 틀린 문장 한 건."""
    sentence: int      # 문장 번호 ⟦n⟧
    report: str        # 번호가 표시된 브리핑 전체 (문맥용)
    correction: str    # 색인에 적힌 올바른 값
    evidence: str      # 그 값이 실린 근거 문장


class ReviserNode(LLMNode):
    name = "reviser"
    template = prompts.TEMPLATE

    def run(self, state: ReviserInput) -> dict:
        try:
            out = self.chain.invoke(state)
        except Exception as e:      # 한 건이 깨져도 나머지는 살린다
            note("reviser", f"⟦{state['sentence']}⟧ failed, keeping original — {type(e).__name__}")
            return {}

        text = " ".join(str(out.content).split())
        if why := _reject(text, state["correction"]):
            note("reviser",
                 f"⟦{state['sentence']}⟧ rejected ({why}), keeping original — {text[:50]}")
            return {}
        return {"fixes": [{"sentence": state["sentence"], "text": text}]}


def _reject(text: str, correction: str) -> str:
    """받을 수 없는 이유. 문장 하나이고, 수정값의 숫자가 들어 있고, 내부 표기가 없어야 받는다."""
    if not text:
        return "empty"
    if "⟦" in text:
        return "marker left in"
    if sentences.count(text + " ") != 1:
        return f"{sentences.count(text + ' ')} sentences"
    if not all(n in text for n in sentences.numbers(correction)):
        return "correction number missing"
    return ""

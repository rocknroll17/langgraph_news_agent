"""checker — 브리핑을 문장 단위로 색인과 대조한다. 글은 고치지 않는다.

문장은 옮겨 적지 않고 번호 ⟦n⟧ 으로 가리킨다. 근거 기사도 번호 [n] 이다.
모델이 낸 번호가 실제로 있는지, 수정값이 근거 문장에 정말 적혀 있는지는
코드가 확인하고, 어긋난 판정은 버린다. 버려진 문장은 원문 그대로 남는다.
"""

from typing import Literal

from pydantic import BaseModel, Field

from nodes.base import LLMNode
from state import State
from utils import articles, note, sentences

from . import prompts


class Verdict(BaseModel):
    sentence: int = Field(description="브리핑의 문장 번호 ⟦n⟧")
    evidence: str = Field(default="", description="색인에서 그대로 옮긴 근거 문장")
    verdict: Literal["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]
    articles: list[int] = Field(default_factory=list, description="근거가 실린 기사 번호 [n]")
    correction: str = Field(default="", description="CONTRADICTED 일 때 색인에 적힌 올바른 값")


class Checked(BaseModel):
    verdicts: list[Verdict]


class CheckerNode(LLMNode):
    name = "checker"
    template = prompts.TEMPLATE

    def __init__(self, model) -> None:
        super().__init__(model)
        self.chain = prompts.TEMPLATE | model.with_structured_output(Checked)

    def run(self, state: State) -> dict:
        index = state.get("articles") or []
        report = "\n".join(str(m.content) for m in state["report"])
        if not index or not report.strip():
            return {"verdicts": []}

        try:
            checked = self.chain.invoke({
                "date": state["date"],
                "index": articles.render(index),
                "report": sentences.mark(report),
            })
        except Exception as e:      # 구조화 출력이 깨지면 검증을 건너뛰고 원문을 살린다
            note("checker", f"verdict failed, keeping draft as-is — {type(e).__name__}")
            return {"verdicts": []}

        verdicts = [v for v in checked.verdicts if _valid(v, sentences.count(report), len(index))]
        _log(checked.verdicts, verdicts)
        return {"verdicts": [v.model_dump() for v in verdicts]}


def _valid(v: Verdict, n_sentences: int, n_articles: int) -> bool:
    """모델이 가리킨 번호와 수정값을 코드가 확인한다. 하나라도 어긋나면 판정을 버린다."""
    if not 1 <= v.sentence <= n_sentences:
        return False
    v.articles = [i for i in v.articles if 1 <= i <= n_articles]
    if v.verdict == "CONTRADICTED":
        # 수정값의 숫자가 근거 문장에 그대로 있어야 한다. 모델이 아는 값이 아니라 색인의 값.
        # 숫자 없는 수정값("출처마다 값이 다름")은 고칠 수 없으니 판정만 낮추고 문장은 둔다.
        nums = sentences.numbers(v.correction)
        if not nums:
            v.verdict = "NOT_ENOUGH_INFO"
            return True
        return all(n in v.evidence for n in nums)
    return v.verdict == "NOT_ENOUGH_INFO" or bool(v.articles)


def _log(raw: list[Verdict], kept: list[Verdict]) -> None:
    """어긋난 항목과 버린 판정만 남긴다. 건수는 Trace 가 이미 보여준다."""
    lines = [f"mismatch  ⟦{v.sentence}⟧ → {v.correction[:45]}"
             for v in kept if v.verdict == "CONTRADICTED"]
    if dropped := len(raw) - len(kept):
        lines.append(f"dropped {dropped} verdict(s) — bad number or correction not in evidence")
    if lines:
        note("checker", *lines)

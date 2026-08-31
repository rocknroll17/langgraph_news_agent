"""checker — 브리핑을 주장 단위로 쪼개 색인과 대조한다. 글은 고치지 않는다."""

from typing import Literal

from openai import APIError
from pydantic import BaseModel, Field

from nodes.base import LLMNode
from state import State
from utils import articles, note

from . import prompts


class Verdict(BaseModel):
    claim: str = Field(description="브리핑에서 뽑은 검증 대상 주장 한 문장")
    evidence: str = Field(default="", description="색인에서 그대로 옮긴 근거 문장")
    verdict: Literal["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]
    media: str = Field(default="", description="근거가 실린 매체명")
    url: str = Field(default="", description="근거 URL")
    correction: str = Field(default="", description="CONTRADICTED 일 때 색인에 적힌 올바른 값")


class Checked(BaseModel):
    verdicts: list[Verdict]


class CheckerNode(LLMNode):
    name = "checker"
    template = prompts.TEMPLATE

    def __init__(self, model) -> None:
        super().__init__(model)
        self.chain = (prompts.TEMPLATE | model.with_structured_output(Checked)).with_retry(
            retry_if_exception_type=(APIError,),
            stop_after_attempt=3,
        )

    def run(self, state: State) -> dict:
        index = state.get("articles") or []
        report = "\n".join(str(m.content) for m in state["report"])
        if not index or not report.strip():
            return {"verdicts": []}

        try:
            checked = self.chain.invoke({
                "date": state["date"],
                "index": articles.render(index),
                "report": report,
            })
        except Exception as e:      # 구조화 출력이 깨지면 검증을 건너뛰고 원문을 살린다
            note("checker", f"verdict failed, keeping draft as-is — {type(e).__name__}")
            return {"verdicts": []}

        _log(checked.verdicts)
        return {"verdicts": [v.model_dump() for v in checked.verdicts]}


def _log(verdicts: list[Verdict]) -> None:
    """어긋난 항목만 남긴다. 건수는 Trace 가 이미 보여준다."""
    if wrong := [v for v in verdicts if v.verdict == "CONTRADICTED"]:
        note("checker", *(f"mismatch  {v.claim[:45]} → {v.correction[:45]}" for v in wrong))

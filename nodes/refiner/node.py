"""refiner — 검색 결과 한 건이 이번 리서치에 쓸 기사인지만 판정한다.

Send 로 기사 수만큼 띄워 병렬 실행한다. 각 인스턴스는 기사 하나만 본다.

본문은 손대지 않는다. Tavily 의 content 는 이미 본문만 발췌한 조각이라
헤더·메뉴 같은 잡동사니가 없고, 모델이 문장을 고쳐 쓰면 수치가 틀어진다.
잡음은 문장 안이 아니라 결과 단위(목록 페이지, 약관, 전망 블로그)로 들어오므로
살릴지 버릴지만 정한다. 출력은 bool 하나 — 작은 모델이 가장 안정적으로 내는 형태다.
"""

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from config import REQUEST
from nodes.base import LLMNode
from utils import note

from . import prompts


class Refined(BaseModel):
    relevant: bool = Field(description="이번 리서치 주제에 쓸 수 있는 기사 본문인지")


class RefinerInput(TypedDict):
    """Send 로 넘어오는 기사 한 건."""
    date: str
    media: str
    title: str
    url: str
    published: str
    content: str


class RefinerNode(LLMNode):
    name = "refiner"
    template = prompts.TEMPLATE

    def __init__(self, model) -> None:
        super().__init__(model)
        self.chain = prompts.TEMPLATE | model.with_structured_output(Refined)

    def run(self, state: RefinerInput) -> dict:
        try:
            out = self.chain.invoke({
                "date": state["date"],
                "request": REQUEST,
                "title": state["title"],
                "published": state["published"],
                "content": state["content"],
            })
        except Exception as e:      # 한 건이 깨져도 나머지는 살린다
            note("refiner", f"failed, keeping article — {type(e).__name__}")
            out = Refined(relevant=True)

        if not out.relevant or not state["content"].strip():
            return {}               # 주제와 무관하거나 빈 결과면 버린다

        return {"articles": [{
            "media": state["media"],
            "title": state["title"],
            "url": state["url"],
            "published": state["published"],
            "content": state["content"],   # 원문 그대로. 수치가 변형될 경로를 남기지 않는다
        }]}

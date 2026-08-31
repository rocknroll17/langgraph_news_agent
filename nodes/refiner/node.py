"""refiner — 검색 결과 한 건에서 기사 본문만 남긴다.

Send 로 기사 수만큼 띄워 병렬 실행한다. 각 인스턴스는 기사 하나만 본다.
입력이 작아서 빠르고, 출력이 정리돼 있어 뒤 단계가 전부 가벼워진다.
"""

from openai import APIError
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from config import REQUEST
from nodes.base import LLMNode
from utils import note

from . import prompts


class Refined(BaseModel):
    relevant: bool = Field(description="금융 시장과 관련 있는 기사인지")
    content: str = Field(default="", description="잡동사니를 걷어낸 기사 본문")


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
        self.chain = (prompts.TEMPLATE | model.with_structured_output(Refined)).with_retry(
            retry_if_exception_type=(APIError,),
            stop_after_attempt=3,
        )

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
            note("refiner", f"failed, keeping raw text — {type(e).__name__}")
            out = Refined(relevant=True, content=state["content"])

        if not out.relevant or not out.content.strip():
            return {}               # 시장과 무관하면 버린다

        return {"articles": [{
            "media": state["media"],
            "title": state["title"],
            "url": state["url"],
            "published": state["published"],
            "content": out.content.strip(),
        }]}

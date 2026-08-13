"""노드 공통 골격."""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from state import State


class Node(ABC):
    """상태를 받아 '바꿀 키만 담은 dict' 을 돌려준다.

    __call__ 이 있어 workflow.add_node(node.name, node) 로 바로 꽂힌다.
    """

    name: str

    def __call__(self, state: State) -> dict:
        return self.run(state)

    @abstractmethod
    def run(self, state: State) -> dict: ...


class LLMNode(Node):
    """프롬프트 템플릿과 모델을 이어 붙인 노드.

    self.chain.invoke(변수dict) 한 번이면 끝난다.
    """

    template: ChatPromptTemplate   # 하위 클래스가 자기 폴더의 prompts.TEMPLATE 를 지정

    def __init__(self, model: BaseChatModel) -> None:
        self.model = model
        self.chain = self.template | model

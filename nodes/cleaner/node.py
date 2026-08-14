"""cleaner — 한 회차가 끝난 뒤 상태를 비운다.

체크포인터를 붙여 같은 thread 로 계속 돌리면 어제 메시지가 그대로 남는다.
검색 원문은 한 번에 수만 자라, 이틀만 쌓여도 컨텍스트가 넘친다.

발행이 끝난 시점에서 다음 회차에 필요한 것은 없다.
어제 브리핑은 reports/ 파일로 남아 planner 가 따로 읽는다.
"""

from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from nodes.base import Node
from state import State


class CleanerNode(Node):
    name = "cleaner"

    def run(self, state: State) -> dict:
        print(f"[cleaner] 메시지 {len(state['messages'])}건 정리, 상태 초기화")
        return {
            # add_messages 리듀서에 RemoveMessage 를 흘리면 해당 메시지가 지워진다
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)],
            "report": [RemoveMessage(id=REMOVE_ALL_MESSAGES)],
            "retry": 0,
            "facts": "",
            "rounds": 0,
            "consumed": 0,
            "read_done": False,
            "articles": None,   # collect 리듀서가 None 을 초기화로 해석한다
            "verdicts": [],
            "cited": "",
            "failed": False,
        }

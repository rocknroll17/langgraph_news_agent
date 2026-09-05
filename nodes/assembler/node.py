"""assembler — 판정과 고친 문장을 번호대로 본문에 끼우고 인용을 단다.

LLM 을 쓰지 않는다. 문장을 갈아 끼우는 것도, URL 을 찾아 붙이는 것도 코드다.
그래서 판정 없는 문장은 바뀔 수 없고, 없는 URL 은 만들어질 수 없다.
"""

from nodes.base import Node
from state import State
from utils import note, sentences


class AssemblerNode(Node):
    name = "assembler"

    def run(self, state: State) -> dict:
        verdicts = state.get("verdicts") or []
        report = "\n".join(str(m.content) for m in state["report"])
        if not verdicts or not report.strip():
            return {}          # 판정이 없으면 writer 원문을 그대로 쓴다

        fixes = {f["sentence"]: f["text"] for f in state.get("fixes") or []}
        cited = sentences.assemble(report, verdicts, fixes, state.get("articles") or [])

        wrong = [v["sentence"] for v in verdicts if v["verdict"] == "CONTRADICTED"]
        note("assembler",
             f"cited {sum(1 for v in verdicts if v['verdict'] == 'SUPPORTED')} sentence(s)",
             f"fixed {len([n for n in wrong if n in fixes])} of {len(wrong)} contradicted")
        return {"cited": cited}

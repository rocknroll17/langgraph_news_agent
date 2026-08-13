"""reviser — checker 의 판정대로 틀린 곳만 고치고 인용을 단다."""

from nodes.base import LLMNode
from state import State

from . import prompts


class ReviserNode(LLMNode):
    name = "reviser"
    template = prompts.TEMPLATE

    def run(self, state: State) -> dict:
        verdicts = state.get("verdicts") or []
        report = "\n".join(str(m.content) for m in state["report"])
        if not verdicts or not report.strip():
            return {}          # 판정이 없으면 writer 원문을 그대로 쓴다

        revised = self.chain.invoke({"verdicts": _render(verdicts), "report": report})
        return {"messages": [revised], "cited": str(revised.content)}


def _render(verdicts: list[dict]) -> str:
    lines = []
    for v in verdicts:
        line = f"- 주장: {v['claim']}\n  판정: {v['verdict']}"
        if v.get("url"):
            line += f"\n  출처: {v.get('media', '')} | {v['url']}"
        if v.get("correction"):
            line += f"\n  올바른 값: {v['correction']}"
        lines.append(line)
    return "\n".join(lines)

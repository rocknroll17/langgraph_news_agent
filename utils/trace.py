"""모델에 무엇이 오갔는지 터미널에 요약해 찍는다.

빌트인(ConsoleCallbackHandler, set_debug)은 실행 전체를 JSON 으로 쏟아내
읽을 수가 없다. 깔끔하게 보려면 LangSmith 를 쓰고, 터미널에서는 이걸 쓴다.

핵심 세 가지:
1. 노드 이름으로 묶는다 — 어느 단계의 호출인지 바로 보이게
2. 이미 찍은 메시지는 다시 찍지 않는다 — messages 는 누적되므로 매번 전체가 나온다
3. 시스템 프롬프트는 첫 줄과 길이만 — 매 호출 같은 내용이라 전문은 소음이다

    from utils.trace import PrettyTrace
    app.stream(state, config={"callbacks": [PrettyTrace()]})
    PrettyTrace(full=True)   # 전문을 봐야 할 때
"""

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


class PrettyTrace(BaseCallbackHandler):
    """LLM 호출과 도구 실행을 한 줄 요약 위주로 찍는다.

    full=True 면 메시지 전문을 찍는다.
    body: 본문을 몇 자까지 보여줄지 (full=False 일 때).
    """

    def __init__(self, full: bool = False, body: int = 400) -> None:
        self.full = full
        self.body = body
        self._seen: set[int] = set()   # 이미 찍은 메시지

    # ── LLM ────────────────────────────────────────────
    def on_chat_model_start(self, serialized, messages: list[list[BaseMessage]], **kw) -> None:
        print(f"\n{BOLD}▶ {_node(kw)}{RESET}")
        for batch in messages:
            fresh = [m for m in batch if id(m) not in self._seen]
            self._seen.update(id(m) for m in fresh)

            # 실제 순서를 그대로 따라간다. 연달아 붙은 ToolMessage 만 한 줄로 접는다.
            # 원문은 이미 도구 실행에서 찍었으니 여기서는 건수와 분량만.
            run: list[BaseMessage] = []
            for m in fresh:
                if type(m).__name__ == "ToolMessage":
                    run.append(m)
                    continue
                _flush_tools(run)
                self._show(m, sent=True)
            _flush_tools(run)

    def on_llm_end(self, response: LLMResult, **kw) -> None:
        print(f"{BOLD}◀ {_node(kw)}{RESET}")
        for generations in response.generations:
            for gen in generations:
                message = getattr(gen, "message", None)
                self._show(message, sent=False) if message else print(self._cut(gen.text))

    # ── 도구 ───────────────────────────────────────────
    def on_tool_end(self, output: Any, **kw) -> None:
        name = kw.get("name") or "tool"
        print(f"  {DIM}🔧 {name} → {len(str(output)):,}자{RESET}")

    def on_tool_error(self, error: BaseException, **kw) -> None:
        print(f"  🔧 {kw.get('name', 'tool')} 실패 — {type(error).__name__}: {error}")

    # ── 내부 ───────────────────────────────────────────
    def _show(self, m: BaseMessage, sent: bool) -> None:
        role = type(m).__name__.replace("Message", "").lower()
        self._seen.add(id(m))
        head = f"  {DIM}{role:9}{RESET}"
        if calls := getattr(m, "tool_calls", None):
            print(f"{head} 도구 호출 {len(calls)}건")
            for c in calls:
                print(f"    {DIM}🔧 {c['name']}({_args(c)}){RESET}")
            return

        content = str(m.content)
        if not content.strip():
            return
        if sent and role == "system" and not self.full:
            # 매 호출 같은 시스템 프롬프트를 전문으로 찍을 이유가 없다
            print(f"{head} {len(content):,}자  {DIM}{content.splitlines()[0][:50]}…{RESET}")
        else:
            print(f"{head} {len(content):,}자\n{_indent(self._cut(content))}")

    def _cut(self, text: str) -> str:
        if self.full or len(text) <= self.body:
            return text
        return f"{text[: self.body]}{DIM} … ({len(text) - self.body:,}자 생략){RESET}"


def _node(kw) -> str:
    return (kw.get("metadata") or {}).get("langgraph_node", "llm")


def _args(call) -> str:
    return ", ".join(f"{k}={str(v)[:60]}" for k, v in call["args"].items())


def _indent(text: str) -> str:
    return "\n".join(f"      {line}" for line in text.splitlines())


def _flush_tools(run: list[BaseMessage]) -> None:
    """연달아 붙은 ToolMessage 를 한 줄로 접어 찍고 버퍼를 비운다."""
    if not run:
        return
    total = sum(len(str(m.content)) for m in run)
    print(f"  {DIM}tool      ×{len(run)}  {total:,}자{RESET}")
    run.clear()

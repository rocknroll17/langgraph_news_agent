"""실행 개형을 터미널에 찍는다.

빌트인(ConsoleCallbackHandler, set_debug)은 실행 전체를 JSON 으로 쏟아내
읽을 수가 없다. 전문은 LangSmith 에 있으니 여기서는 흐름만 본다.

    from utils import Trace
    trace = Trace()
    app.invoke(state, config={"callbacks": [trace]})
    trace.summary()

노드 하나가 블록 하나다. 그 호출이 실제로 받은 것을 전부 보여준다.
프롬프트는 앞부분과 길이만 보여준다.
도구 호출 인자는 자르지 않는다 — 무엇을 찾으려 했는지가 핵심이다.
"""

import ast
import json
import time
import unicodedata
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

HEAD = 50      # 본문을 보여줄 폭 (한글은 두 칸으로 센다)
WIDTH = 68     # 블록 헤더 너비
ROLE = 13      # 이름 칸 너비. read_articles(13자)까지 들어가야 글자 수 칸이 안 밀린다
INJECTED = {"articles"}   # 그래프가 채워 넣는 인자. 모델이 정한 게 아니라 보여줄 이유가 없다
INDENT = " " * (3 + ROLE + 1)   # 이름 칸을 건너뛴 자리. 딸린 줄은 여기서 시작한다


class Trace(BaseCallbackHandler):
    """LLM 호출과 도구 실행을 노드 단위로 묶어 찍는다."""

    def __init__(self) -> None:
        self._begin = time.time()
        self._calls = 0
        self._tokens = [0, 0]
        # refiner 는 기사 수만큼 병렬로 돈다. 버퍼를 하나만 두면 서로 덮어쓴다.
        self._open: dict[Any, tuple[float, str, list[str]]] = {}   # run_id -> (시작, 노드, 줄)
        self._tools: list[str] = []      # 도구 실행 줄. LLM 블록과 섞이지 않게 따로 모은다
        self._tool_node = ""
        self._args: dict[Any, str] = {}   # run_id -> 인자. 인자는 start, 결과는 end 로 온다

    # ── LLM ────────────────────────────────────────────
    def on_chat_model_start(self, serialized, messages: list[list[BaseMessage]], **kw) -> None:
        self._flush_tools()
        lines: list[str] = []
        for batch in messages:
            lines += _input(batch)
        self._open[kw.get("run_id")] = (time.time(), _node(kw), lines)

    def on_llm_end(self, response: LLMResult, **kw) -> None:
        self._calls += 1
        usage = (response.llm_output or {}).get("token_usage") or {}
        self._tokens[0] += usage.get("prompt_tokens", 0)
        self._tokens[1] += usage.get("completion_tokens", 0)

        started, node, lines = self._open.pop(kw.get("run_id"), (time.time(), "llm", []))
        for generations in response.generations:
            for gen in generations:
                lines += _render("ai", getattr(gen, "message", None) or gen.text)
        self._print(node, time.time() - started, lines)

    # ── 도구 ───────────────────────────────────────────
    def on_tool_start(self, serialized, input_str: str, **kw) -> None:
        """인자는 여기로만 온다. 결과가 올 때 같이 찍으려고 붙들어 둔다."""
        self._args[kw.get("run_id")] = _args(kw.get("inputs") or input_str)

    def on_tool_end(self, output: Any, **kw) -> None:
        name = kw.get("name") or "tool"
        body = str(getattr(output, "content", output))   # ToolMessage 로 올 때가 있다
        titles = _titles(body)
        self._tool_node = _node(kw, "") or self._tool_node

        self._tools.append(_row(name, f"{len(titles)} results" if titles else "", len(body)))
        for label, value in self._args.pop(kw.get("run_id"), []):
            self._tools.append(f"{INDENT}{label:7} {value}")   # 인자는 자르지 않는다
        self._tools += [f"{INDENT}result  {_clip(t, 58)}".rstrip() for t in titles]

    def on_tool_error(self, error: BaseException, **kw) -> None:
        self._tools.append(f"   {kw.get('name', 'tool')} failed — {type(error).__name__}")

    # ── 마무리 ─────────────────────────────────────────
    def summary(self) -> None:
        self._flush_tools()
        print(f"\n{time.time() - self._begin:.0f}s · {self._calls} LLM calls · "
              f"{self._tokens[0]:,} in / {self._tokens[1]:,} out tokens", flush=True)

    # ── 내부 ───────────────────────────────────────────
    def _flush_tools(self) -> None:
        """모아둔 도구 실행을 제 블록으로 내보낸다."""
        if self._tools:
            self._print(self._tool_node or "tools", 0.0, self._tools)
            self._tools, self._tool_node = [], ""

    def _print(self, node: str, seconds: float, lines: list[str]) -> None:
        """블록 하나를 print 한 번으로 내보낸다.
        refiner 는 기사 수만큼 병렬로 도는데, 나눠 찍으면 서로 끼어들어 뒤섞인다.
        """
        print("\n".join([f"\n{_head(node)} {seconds:.1f}s", *lines]), flush=True)


def note(node: str, *lines: str) -> None:
    """LLM 을 쓰지 않는 노드가 남기는 블록.

    reporter 처럼 부수효과만 내는 노드는 콜백이 안 울려 Trace 가 못 본다.
    직접 부르되 모양은 같게 맞춘다 — 로그 형식은 이 파일 하나만 안다.
    """
    print("\n".join([f"\n{_head(node)}", *(f"   {line}" for line in lines)]), flush=True)


def _head(node: str) -> str:
    return f"── {node} " + "─" * max(1, WIDTH - len(node))


def _input(batch: list[BaseMessage]) -> list[str]:
    """받은 메시지들. 연달아 붙은 도구 결과는 한 줄로 접는다."""
    lines: list[str] = []
    run: list[BaseMessage] = []

    def fold() -> None:
        if run:
            body = " ".join(str(run[0].content).split())
            size = sum(len(str(m.content)) for m in run)
            lines.append(_row("tool", f"×{len(run)} {body}", size))
            run.clear()

    for m in batch:
        if _role(m) == "tool":
            run.append(m)
            continue
        fold()
        lines += _render(_role(m), m)
    fold()
    return lines


def _render(role: str, message) -> list[str]:
    """한 줄, 또는 도구 호출이면 이름 한 줄 + 인자 여러 줄."""
    if calls := getattr(message, "tool_calls", None):
        names = "/".join(dict.fromkeys(c["name"] for c in calls))
        return [f"   {role:{ROLE}} {names} ×{len(calls)}"] + [
            f"{INDENT}{label:7} {value}" for c in calls for label, value in _args(c["args"])
        ]

    text = " ".join(str(getattr(message, "content", message)).split())
    if not text:
        return []
    if role == "system":
        return [_row(role, "[system prompt]", len(text))]
    return [_row(role, *_unwrap(text))]


def _unwrap(text: str) -> tuple[str, int]:
    """구조화 출력이면 껍데기 대신 알맹이를 보여준다.

    {"relevant": true, "content": "..."} 를 그대로 찍으면 앞 30자가
    전부 키 이름이라 아무것도 안 보인다.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, len(text)
    if not isinstance(data, dict):
        return text, len(text)

    body = max((v for v in data.values() if isinstance(v, str)), key=len, default="")
    if body:
        flags = " ".join(f"{k}={v}" for k, v in data.items() if isinstance(v, bool))
        return (f"{flags} {body}".strip(), len(body))

    if data.get("relevant") is False:
        return "relevant=False — dropped, off-topic", len(text)

    # 본문이 없는 스키마(checker 의 판정 목록 등)는 모양만 보여준다
    shape = " ".join(f"{k} ×{len(v)}" if isinstance(v, list) else f"{k}={v}"
                     for k, v in data.items() if not (isinstance(v, str) and not v))
    return shape, len(text)


def _row(role: str, text: str, size: int) -> str:
    """이름 · 본문 · 글자 수. 세 칸 너비를 고정해 글자 수가 한 줄로 맞게 선다."""
    return f"   {role:{ROLE}} {_clip(text)} {size:>10,}"


def _clip(text: str, width: int = HEAD) -> str:
    """한글은 터미널에서 두 칸을 먹는다. 폭 기준으로 자르고 채운다.
    개행이 섞여 있으면 한 줄로 접는다 — 표가 어긋나지 않게.
    """
    out, used = [], 0
    for ch in " ".join(str(text).split()):
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + w > width:
            break
        out.append(ch)
        used += w
    return "".join(out) + " " * (width - used)


def _args(args) -> list[tuple[str, str]]:
    """인자를 (이름, 값) 목록으로. 이름은 도구가 실제로 받는 파라미터명이다.

    InjectedState 로 채워지는 인자는 모델이 정한 게 아니라 그래프가 넣은 것이라 뺀다.
    """
    if not isinstance(args, dict):
        return [("args", str(args))] if args else []
    return [(k, str(v)) for k, v in args.items() if k not in INJECTED]


def _titles(output: str) -> list[str]:
    """검색 결과면 기사 제목들. 무엇을 물어 무엇이 왔는지 보인다."""
    try:
        payload = ast.literal_eval(output)
    except (ValueError, SyntaxError):
        return []
    if not isinstance(payload, dict):
        return []
    return [(r.get("title") or "").strip() for r in payload.get("results") or []]


def _role(message) -> str:
    return type(message).__name__.replace("Message", "").lower()


def _node(kw, default: str = "llm") -> str:
    return (kw.get("metadata") or {}).get("langgraph_node") or default

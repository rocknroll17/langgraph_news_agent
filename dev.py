"""개발용 실행기 — 노드별 상태를 저장해두고 원하는 노드만 다시 돌린다.

프롬프트를 고칠 때마다 처음부터 4분씩 돌릴 이유가 없다.
한 번 모아두면 그다음부터는 고친 노드만 몇 초에 확인할 수 있다.

    uv run python dev.py collect          전체를 돌리며 노드마다 상태 저장
    uv run python dev.py collect writer   writer 직전까지만 돌리고 멈춤
    uv run python dev.py run writer       저장해 둔 상태로 writer 만 실행
    uv run python dev.py show writer      writer 가 받을 입력을 확인만

검색은 SEARCH_CACHE=1 로 캐시되므로 Tavily 쿼터를 쓰지 않는다.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("SEARCH_CACHE", "1")

from langchain_core.load import dumpd, load
from langgraph.checkpoint.memory import MemorySaver

import main
from nodes import (
    CheckerNode,
    FollowUpNode,
    ReporterNode,
    ReviserNode,
    SynthesizerNode,
    WriterNode,
)

STATE_DIR = Path(__file__).parent / ".dev_state"

NODES = {n.name: n for n in (SynthesizerNode, FollowUpNode, WriterNode,
                             CheckerNode, ReviserNode, ReporterNode)}


def _path(node: str) -> Path:
    return STATE_DIR / f"{node}.json"


def load_state(node: str) -> dict:
    """저장해 둔 상태. date 는 문자열로 담겨 있어 되돌린다."""
    path = _path(node)
    if not path.exists():
        sys.exit(f"{path} 가 없습니다. 먼저 `dev.py collect` 를 돌리세요.")
    state = load(json.loads(path.read_text(encoding="utf-8")))
    state["date"] = date.fromisoformat(state["date"])
    return state


def collect(stop: str | None = None) -> None:
    """그래프를 돌리며 각 노드 진입 직전의 상태를 저장한다.

    체크포인터를 붙이면 스냅샷마다 '다음에 돌 노드'(next)가 남는다.
    그걸 파일 이름으로 삼으면 어느 노드의 입력인지 헷갈릴 일이 없다.
    """
    app = main.build_graph(
        checkpointer=MemorySaver(),
        interrupt_before=[stop] if stop else None,
    )
    config = {"configurable": {"thread_id": "dev"}}
    app.invoke(main.initial_state(), config=config)

    STATE_DIR.mkdir(exist_ok=True)
    saved = set()
    for snap in app.get_state_history(config):
        node = snap.next[0] if snap.next else None
        if node in NODES and node not in saved:
            # date 객체는 LangChain 직렬화가 못 다룬다. 문자열로 눕혀 담는다.
            values = {**snap.values, "date": str(snap.values["date"])}
            _path(node).write_text(
                json.dumps(dumpd(values), ensure_ascii=False), encoding="utf-8")
            saved.add(node)

    print("저장:", ", ".join(sorted(saved)) or "없음")


def run(node: str) -> None:
    state = load_state(node)
    cls = NODES[node]
    inst = cls() if node == ReporterNode.name else cls(main.build_model())

    print(f"── {node} 실행\n")
    out = inst.run(state)
    for key, value in out.items():
        if key == "messages":
            for m in value:
                print(f"[{type(m).__name__}]")
                if getattr(m, "tool_calls", None):
                    for c in m.tool_calls:
                        print(f"  🔧 {c['name']}({c['args']})")
                print(m.content)
        else:
            print(f"\n[{key}] {str(value)[:2000]}")


def show(node: str) -> None:
    state = load_state(node)
    print(f"── {node} 가 받을 상태\n")
    for key in ("date", "rounds", "consumed", "read_done"):
        if key in state:
            print(f"  {key:10} {state[key]}")
    print(f"  {'articles':10} {len(state.get('articles') or [])}건")
    print(f"  {'facts':10} {len(state.get('facts') or ''):,}자")
    print(f"  {'messages':10} {len(state.get('messages') or [])}건")
    if state.get("facts"):
        print(f"\n── facts\n{state['facts'][:2000]}")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["collect"]
    target = rest[0] if rest else None

    if cmd == "collect":
        collect(target)
    elif cmd in ("run", "show") and target in NODES:
        (run if cmd == "run" else show)(target)
    else:
        sys.exit(f"사용법: dev.py collect|run|show [{'|'.join(NODES)}]")

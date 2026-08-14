"""검색 결과 캐시.

config 가 이 모듈을 쓰므로 utils 패키지 밖에 둔다.
(utils 는 config 를 참조해서 넣으면 순환 참조가 된다.)

같은 검색어를 반복해서 던지면 Tavily 쿼터만 축난다. 시험 삼아 돌릴 때는
저장해 둔 결과를 그대로 쓴다.

    SEARCH_CACHE=1 uv run python main.py    캐시 읽고 쓰기 (시험용)
    (기본값)                                 캐시 안 씀 (운영)

키는 검색어의 해시다. 날짜별로 나눠 담아 어제 결과가 오늘 섞이지 않게 한다.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CACHE_DIR = Path(__file__).resolve().parent / ".search_cache"


def enabled() -> bool:
    return os.environ.get("SEARCH_CACHE") == "1"


def _path(query: str) -> Path:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    key = hashlib.sha1(query.encode()).hexdigest()[:16]
    return CACHE_DIR / str(today) / f"{key}.json"


def get(query: str) -> str | None:
    p = _path(query)
    if not p.exists():
        return None
    print(f"[cache] hit — {query[:50]}")
    return json.loads(p.read_text(encoding="utf-8"))["result"]


def put(query: str, result: str) -> None:
    p = _path(query)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"query": query, "result": result}, ensure_ascii=False),
                 encoding="utf-8")

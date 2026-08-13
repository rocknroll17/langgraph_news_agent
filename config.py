"""환경 설정 한 곳 모음 — 모델, 도구, 상수.

노드들은 여기서만 모델과 도구를 가져간다. 각자 만들지 않는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

ROOT = Path(__file__).resolve().parent

# 실행 위치와 무관하게 이 파일 옆의 .env 를 읽는다
load_dotenv(ROOT / ".env")


# ── 모델 ────────────────────────────────────────────────
# base_url 과 api_key 는 .env(OPENAI_BASE_URL / OPENAI_API_KEY)에서 자동으로 읽힌다.
# 모델 ID 만 명시한다 — LangSmith 트레이스에 실제 모델명이 남게 하기 위함.
def build_model(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ["LOCAL_MODEL"],
        temperature=temperature,
    )


# ── 도구 ────────────────────────────────────────────────
def build_search_tool() -> BaseTool:
    """뉴스 검색 도구.

    TavilySearch 를 그대로 bind 하면 모델이 start_date/end_date 까지 채워 보내는데,
    우리가 고정해 둔 time_range 와 충돌해 Tavily 가 400 을 돌려준다.
        Error 400: When time_range is set, start_date or end_date cannot be set

    그래서 query 하나만 받는 얇은 도구로 감싼다.
    기간·건수·깊이는 코드가 정하고, 모델은 검색어만 정한다.
    """
    tavily = TavilySearch(
        max_results=5,
        topic="news",
        time_range="day",       # 오늘 기사만 — "오늘 것만 쓰라"는 규칙을 코드로 강제
        search_depth="advanced",
    )

    @tool
    def search_news(query: str) -> str:
        """오늘 자 뉴스를 검색한다. 검색어는 영어로 쓸 것."""
        # callbacks=[] 로 잘라준다. 안 그러면 안쪽 tavily 호출까지 트레이스에 두 번 찍힌다.
        return str(tavily.invoke({"query": query}, config={"callbacks": []}))

    return search_news


# ── 상수 ────────────────────────────────────────────────
MIN_CALLS, MAX_CALLS = 4, 6   # planner 가 한 번에 발행할 검색 횟수 범위
MAX_RETRY = 2                 # planner 재시도 상한 (무한 루프 방지)
PREV_DAYS = 2                 # planner 에게 붙일 과거 브리핑 개수

REPORTS_DIR = ROOT / "reports"

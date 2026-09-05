"""환경 설정 한 곳 모음 — 모델, 도구, 상수.

노드들은 여기서만 모델과 도구를 가져간다. 각자 만들지 않는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

import cache

ROOT = Path(__file__).resolve().parent

# 실행 위치와 무관하게 이 파일 옆의 .env 를 읽는다.
# 로컬에서는 .env.dev 가 그 위를 덮는다 — 운영 채널로 시험 발송하는 사고를 막는다.
# CI(GitHub Actions)에서는 .env.dev 가 없고 값은 저장소 Secrets 에서 온다.
load_dotenv(ROOT / ".env")
if not os.environ.get("CI"):
    load_dotenv(ROOT / ".env.dev", override=True)


# ── 모델 ────────────────────────────────────────────────
# base_url 과 api_key 는 .env(OPENAI_BASE_URL / OPENAI_API_KEY)에서 자동으로 읽힌다.
# 모델 ID 만 명시한다 — LangSmith 트레이스에 실제 모델명이 남게 하기 위함.
def build_model(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ["LOCAL_MODEL"],
        temperature=temperature,
    )


# ── 검색 허용 도메인 ──────────────────────────────────────
# 검색 결과의 품질은 문장을 다듬어서가 아니라 입구에서 정해진다.
# 브리핑에서 틀린 수치는 예외 없이 2차 사이트(요약 블로그, 예측시장, 집계 사이트)에서
# 왔고, 주요 매체·기관 인용은 맞았다. 그래서 통신사·경제지·기관·거래소로 제한한다.
#
# 표기 규칙 (Tavily 실측):
#   - 루트 도메인만 적는다. "nikkei.com" 이 asia.nikkei.com 까지 잡는다.
#   - 와일드카드("*.nikkei.com")를 넣으면 필터가 깨져 아무 사이트나 들어온다. 쓰지 않는다.
#   - 라이브러리 상한은 150개.
SEARCH_DOMAINS = [
    # 통신사
    "reuters.com", "apnews.com", "afp.com", "yna.co.kr",
    # 경제·금융 전문지 (미국·유럽)
    "bloomberg.com", "cnbc.com", "ft.com", "wsj.com", "barrons.com", "economist.com",
    "marketwatch.com", "investors.com", "fortune.com", "foxbusiness.com",
    "finance.yahoo.com", "morningstar.com", "investing.com", "tradingeconomics.com",
    # 종합 일간지·방송 (금융·정책 보도)
    "nytimes.com", "washingtonpost.com", "theguardian.com", "bbc.com", "bbc.co.uk",
    "cnn.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com", "npr.org",
    "axios.com", "politico.com", "thehill.com", "dw.com", "france24.com",
    # 아시아 매체 (영문)
    "nikkei.com", "japantimes.co.jp", "asahi.com", "mainichi.jp", "nhk.or.jp",
    "scmp.com", "caixinglobal.com", "straitstimes.com", "businesstimes.com.sg",
    "channelnewsasia.com", "kedglobal.com", "koreaherald.com", "koreatimes.co.kr",
    "koreajoongangdaily.joins.com", "hani.co.kr", "mk.co.kr",
    "economictimes.indiatimes.com", "livemint.com", "business-standard.com",
    # 중동·에너지
    "thenationalnews.com", "arabnews.com", "gulfnews.com", "oilprice.com",
    # 중앙은행·정부·통계 (1차 자료)
    "federalreserve.gov", "stlouisfed.org", "newyorkfed.org", "bls.gov", "bea.gov",
    "census.gov", "treasury.gov", "sec.gov", "cbo.gov", "eia.gov", "whitehouse.gov",
    "ecb.europa.eu", "bankofengland.co.uk", "europa.eu", "boj.or.jp", "bok.or.kr",
    "pbc.gov.cn", "stats.gov.cn", "imf.org", "worldbank.org", "bis.org", "oecd.org",
    "opec.org", "iea.org",
    # 거래소·지수 제공사
    "nasdaq.com", "nyse.com", "spglobal.com", "cmegroup.com", "cboe.com",
    "lseg.com", "jpx.co.jp", "hkex.com.hk", "krx.co.kr",
]


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
        include_domains=SEARCH_DOMAINS,   # 입구에서 2차 사이트를 거른다
    )

    @tool
    def search_news(query: str) -> str:
        """오늘 자 뉴스를 검색한다. 검색어는 영어로 쓸 것."""
        if cache.enabled() and (hit := cache.get(query)) is not None:
            return hit

        # callbacks=[] 로 잘라준다. 안 그러면 안쪽 tavily 호출까지 트레이스에 두 번 찍힌다.
        result = str(tavily.invoke({"query": query}, config={"callbacks": []}))

        if cache.enabled():
            cache.put(query, result)
        return result

    return search_news


# ── 리서치 주제 ─────────────────────────────────────────
# planner 가 검색어를 만들 때, refiner 가 "쓸 내용" 을 가릴 때 같은 기준을 쓴다.
REQUEST = (
    "오늘 미국 증시와 세계 시장의 변동, "
    "그리고 미국 정치 중 금융 관련 이슈를 조사해 브리핑하세요."
)


# ── 상수 ────────────────────────────────────────────────
MIN_CALLS, MAX_CALLS = 4, 6   # planner 가 한 번에 발행할 검색 횟수 범위
MAX_RETRY = 2                 # planner 재시도 상한 (무한 루프 방지)
PREV_DAYS = 2                 # planner 에게 붙일 과거 브리핑 개수
FOLLOWUP_CALLS = 3            # follow_up 이 추가로 발행할 검색 상한
MAX_ROUNDS = 2                # synthesizer 회차 상한 (1차 + 추가조사 1회)
MAX_READ_ROUNDS = 3           # writer 가 기사를 꺼내 읽을 수 있는 횟수

REPORTS_DIR = ROOT / "reports"

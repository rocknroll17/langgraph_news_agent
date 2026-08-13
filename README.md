# 시장 브리핑 에이전트

매일 아침 미국·세계 증시 뉴스를 검색해서, **사실검증을 거친** 브리핑으로 만들어 디스코드로 보낸다.
LangGraph 로 짠 8노드 파이프라인.

LLM 은 OpenAI 호환 엔드포인트면 무엇이든 된다. 이 저장소는 로컬 llama.cpp(gemma4) 로 돌린다.

---

## 왜 노드를 이렇게 나눴나

작은 로컬 모델에게 "검색 결과 읽고 좋은 글 써줘" 를 한 번에 시키면 실패한다.
원문을 대충 읽고, 수치를 흘리고, 없는 사실을 지어낸다.

그래서 한 노드에 한 가지 일만 시킨다.

```
planner ─(검색 충분)→ search → synthesizer → writer → checker → reviser → reporter → cleaner → END
   │ ▲
   │ └─(검색 부족, 재시도)
   └───(끝내 못 구함)──────────→ synthesizer
```

| 노드 | 하는 일 | LLM |
|---|---|---|
| **planner** | 검색어를 한 번에 4~6개 발행한다. 답은 쓰지 않는다 | ○ |
| **search** | `ToolNode` 로 Tavily 검색을 병렬 실행 (5건 22초 → 5.7초) | |
| **synthesizer** | 검색 원문에서 사실만 추출. 주장끼리 인과·대조를 표시 | ○ |
| **writer** | 사실 목록을 읽히는 글로. 검색 원문은 보지 않는다 | ○ |
| **checker** | 주장 단위로 쪼개 원문 색인과 대조, 판정만 한다 | ○ |
| **reviser** | 판정대로 틀린 곳만 고치고 인용을 단다 | ○ |
| **reporter** | 파일로 저장하고 디스코드로 발송 | |
| **cleaner** | 상태 초기화 (다음 회차용) | |

### 사실검증이 실제로 잡아내는 것

```
[checker] 주장 16건 — 근거있음 9 / 어긋남 1 / 근거없음 6
   ✗ 다우존스 0.04% 하락 53,770.27  → 색인값: 0.06% 하락 53,762.05
   ✗ 상하이 종합지수 0.50% 하락      → 색인값: 0.32% 상승
```

writer 가 흘린 수치를 checker 가 원문과 대조해 잡고, reviser 가 그 부분만 고친다.

---

## 설계 노트

### 프롬프트가 아니라 코드로 강제하는 것들

프롬프트로 부탁해서 지켜지지 않는 것들은 코드가 처리한다.

| 문제 | 처리 |
|---|---|
| 모델이 "최대 6회" 를 어긴다 | `tool_calls[:MAX_CALLS]` 로 자른다 |
| 오래된 기사를 오늘 것처럼 쓴다 | Tavily `time_range="day"` 고정 |
| 모델이 `start_date` 를 넣어 400 을 낸다 | `query` 만 받는 얇은 도구로 감싼다 |
| 출처 URL 을 흘린다 | 검증 색인을 코드가 만들어 넘긴다 |
| "없음" 만 적힌 빈 섹션을 만든다 | 발행 직전에 제목째 걷어낸다 |

### 데이터를 시스템 프롬프트에 넣지 않는다

시스템에는 역할과 규칙만, 실제 데이터는 사용자 발화로 준다.
데이터를 시스템 프롬프트에 끼워 넣으면 작은 모델이 "예시 자리" 로 읽고
"자료를 주세요" 라고 되묻는다.

### 지난 브리핑을 참고 자료로 붙인다

`reports/` 에 남은 어제 브리핑을 planner 에게 **HumanMessage 로** 붙인다.
AIMessage 로 붙이면 모델이 "내가 이미 답했다" 고 읽고 검색을 건너뛴다.

덕분에 이미 다룬 이슈는 후속 전개를 찾고, 지난번에 못 구한 항목은 다시 찾는다.

---

## 실행

### 준비

```bash
git clone https://github.com/rocknroll17/langgraph_news_agent.git
cd langgraph_news_agent
cp .env.example .env      # 키 채우기
uv sync
```

### 돌리기

```bash
uv run python main.py             # 조용히
TRACE=1 uv run python main.py     # 노드별로 무엇이 오갔는지
TRACE=full uv run python main.py  # 프롬프트·응답 전문
```

`TRACE=1` 출력:

```
▶ planner
  system    1,895자  당신은 리서치 팀의 리드입니다.…
  human       312자
      아래는 지난 브리핑입니다. …
◀ planner
  ai        도구 호출 5건
    🔧 search_news(query=S&P 500 Nasdaq Dow Jones close August 13 2026)
    🔧 search_news(query=STOXX 600 DAX FTSE 100 August 13 2026)
  🔧 search_news → 9,042자
  🔧 search_news → 11,199자

▶ synthesizer
  system    1,219자  당신은 리서치 팀의 리서처입니다.…
  tool      ×5  48,240자
◀ synthesizer
  ai        2,508자
      [미국 증시]
      - S&P 500 종가 7,748.50, +0.3% | Zacks, Reuters | https://…
```

---

## 자동 실행

`.github/workflows/daily-briefing.yml` 이 매일 10:00(KST)에 돈다.
GitHub 러너가 그때만 켜져서 실행되고 끝나면 사라진다. 상시 서버가 없다.

브리핑은 `reports/` 에 커밋된다. 러너는 매번 새 머신이라,
다음 실행의 planner 가 어제 것을 읽으려면 저장소에 남아야 하기 때문이다.

저장소 **Settings → Secrets and variables → Actions** 에 등록할 값:

| 종류 | 이름 |
|---|---|
| Variables | `OPENAI_BASE_URL`, `LOCAL_MODEL` |
| Secrets | `OPENAI_API_KEY`, `TAVILY_API_KEY`, `DISCORD_WEBHOOK_URL`, `LANGSMITH_API_KEY` |

---

## 구조

```
main.py            그래프 조립만
config.py          모델·도구·상수
state.py           그래프 상태와 리듀서
nodes/
  base.py          Node / LLMNode 공통 골격
  <노드>/
    node.py        로직
    prompts.py     프롬프트 + ChatPromptTemplate
utils/
  storage.py       reports/ 읽기·쓰기
  discord.py       웹훅 발송 (2000자 분할, 429 재시도)
  text.py          인용 색인, 본문 정리
  trace.py         터미널 트레이스
```

프롬프트 조립은 직접 만들지 않고 LangChain 의 `ChatPromptTemplate` 을 공통 빌더로 쓴다.
노드 폴더는 문구와 템플릿 정의만 갖고, 변수 치환과 모델 연결은 `template | model` 이 처리한다.

---

## 라이선스

MIT

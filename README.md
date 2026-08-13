# 시장 브리핑 에이전트

매일 아침 미국·유럽·아시아 증시 뉴스를 모아 브리핑으로 정리하고 디스코드로 보냅니다. 쓴 내용이 검색 결과와 맞는지 확인하는 단계가 들어 있습니다. LangGraph로 만든 8노드 파이프라인입니다.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green">
</p>

LLM은 OpenAI 호환 엔드포인트면 무엇이든 됩니다. `.env`의 주소만 바꾸면 됩니다.

---

## 왜 이렇게 나눴나

"검색 결과 읽고 브리핑 써줘"를 한 번에 시키면 잘 안 됩니다. 원문을 대충 읽고, 숫자를 틀리고, 검색에 없던 내용을 지어냅니다. 모델이 작을수록 심합니다.

그래서 **한 노드가 한 가지 일만** 하게 나눴습니다. 검색 계획, 사실 뽑기, 글쓰기, 검증, 교정을 따로 돌리고, 각 노드는 앞 노드 결과만 봅니다.

```mermaid
flowchart LR
    P[planner] -->|검색 충분| S[search]
    P -.->|검색 부족 · 재시도| P
    P -.->|끝내 못 구함| SY
    S --> SY[synthesizer]
    SY --> W[writer]
    W --> C[checker]
    C --> R[reviser]
    R --> RP[reporter]
    RP --> CL[cleaner]
    CL --> E([END])
```

| 노드 | 하는 일 | LLM |
|:--|:--|:-:|
| `planner` | 검색어를 한 번에 4~6개 만든다. 답은 쓰지 않는다 | ● |
| `search` | `ToolNode`로 Tavily 검색을 동시에 돌린다 | |
| `synthesizer` | 검색 원문에서 사실만 뽑고, 사실끼리 인과·대조를 표시한다 | ● |
| `writer` | 뽑아둔 사실로 글을 쓴다. 검색 원문은 보지 않는다 | ● |
| `checker` | 글을 문장 단위로 쪼개 원문과 맞춰본다. 판정만 한다 | ● |
| `reviser` | 판정대로 틀린 곳만 고치고 인용을 단다 | ● |
| `reporter` | 파일로 저장하고 디스코드로 보낸다 | |
| `cleaner` | 다음 회차를 위해 상태를 비운다 | |

---

## 사실 확인

`writer`가 쓴 글을 `checker`가 문장 단위로 쪼개서 검색 원문과 하나씩 맞춰봅니다. 판정은 `SUPPORTED` / `CONTRADICTED` / `NOT_ENOUGH_INFO` 셋 중 하나고, `reviser`가 그 결과대로 틀린 부분만 고칩니다.

```
[checker] 주장 16건 — 근거있음 9 / 어긋남 1 / 근거없음 6
   ✗ 다우존스 0.04% 하락 53,770.27  →  색인값: 0.06% 하락 53,762.05
   ✗ 상하이 종합지수 0.50% 하락      →  색인값: 0.32% 상승
```

판정과 수정을 나눈 이유는 한 번에 둘 다 시키면 둘 다 대충 하기 때문입니다. **문장 쪼개기 → 근거 먼저 찾기 → 틀린 데만 고치기** 순서로 돌립니다.

**보내는 결과물**

> ### 오늘 한눈에
> 미국 증시는 AI 관련 기술주가 오르면서 상승 마감했습니다. 7월 소비자물가지수가 예상보다 낮게 나와 연준이 금리를 동결할 거라는 전망이 늘었습니다.
>
> ### 미국 증시
> S&P 500은 0.3% 올라 7,748.50에 마감했고, 나스닥 종합지수도 0.54% 오른 26,588.49를 기록했습니다([Zacks](https://example.com), [Reuters](https://example.com)). 다만 다우존스 산업평균지수는 0.06% 내린 53,762.05로 마감해 지수마다 방향이 달랐습니다([TS2](https://example.com)).

---

## 만들면서 정한 것

### 프롬프트로 부탁하지 말고 코드로 막는다

프롬프트에 써놔도 안 지켜지는 게 있습니다. 그런 건 코드에서 처리합니다.

| 문제 | 처리 |
|:--|:--|
| "최대 6회"라고 써도 더 부른다 | `tool_calls[:MAX_CALLS]`로 자른다 |
| 오래된 기사를 오늘 것처럼 쓴다 | Tavily `time_range="day"`로 고정 |
| 모델이 `start_date`를 넣어 API가 400을 뱉는다 | `query`만 받는 도구로 감싼다 |
| 출처 URL을 빠뜨리거나 바꿔 쓴다 | 검증용 색인을 코드에서 만들어 넘긴다 |
| "없음"만 적힌 빈 섹션을 만든다 | 보내기 직전에 제목까지 지운다 |

### 데이터는 시스템 프롬프트에 넣지 않는다

시스템 메시지에는 역할과 규칙만 넣고, 실제 데이터는 사용자 메시지로 줍니다. 데이터를 시스템 프롬프트 안에 넣으면 모델이 그걸 예시로 읽고 "자료를 주세요"라고 되묻습니다.

### 어제 브리핑을 참고 자료로 붙인다

`reports/`에 쌓인 어제 브리핑을 `planner`에 **`HumanMessage`로** 붙입니다. `AIMessage`로 붙이면 모델이 자기가 이미 답한 걸로 알고 검색을 건너뜁니다.

이렇게 하면 어제 다룬 이슈는 그 뒤 어떻게 됐는지 찾고, 어제 못 구한 항목은 다시 찾습니다.

---

## 실행

### 설치

```bash
git clone https://github.com/rocknroll17/langgraph_news_agent.git
cd langgraph_news_agent
cp .env.example .env      # 키 채우기
uv sync
```

### 명령

```bash
uv run python main.py             # 그냥 실행
TRACE=1 uv run python main.py     # 노드별로 뭐가 오갔는지
TRACE=full uv run python main.py  # 프롬프트·응답 전문
```

`TRACE=1` 출력

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

`.github/workflows/daily-briefing.yml`이 매일 10시(KST)에 돕니다. GitHub 러너가 그때만 켜졌다 꺼지니까 서버를 따로 안 띄워도 됩니다.

만든 브리핑은 `reports/`에 커밋합니다. 러너는 매번 새 머신이라, 다음 회차의 `planner`가 어제 것을 읽으려면 저장소에 남아 있어야 합니다.

### 환경 분리

| 환경 | 언제 도나 | 보내는 채널 | `reports/` 커밋 |
|:--|:--|:--|:-:|
| `prod` | 스케줄 (매일 10시 KST) | 운영 채널 | ● |
| `dev` | 수동 실행 기본값 | 시험 채널 | ○ |

`dev`는 `DISCORD_WEBHOOK_URL`만 따로 갖고, 나머지는 저장소 값을 씁니다. 시험 삼아 돌린 게 운영 채널로 나가거나 저장소에 커밋되지 않습니다.

수동으로 돌릴 때는 **Actions → 시장 브리핑 → Run workflow**에서 환경을 고릅니다.

### 등록할 값

**Settings → Secrets and variables → Actions**

| 종류 | 이름 |
|:--|:--|
| Variables | `OPENAI_BASE_URL`, `LOCAL_MODEL`, `LANGSMITH_PROJECT` |
| Secrets | `OPENAI_API_KEY`, `TAVILY_API_KEY`, `DISCORD_WEBHOOK_URL`, `LANGSMITH_API_KEY` |

**Settings → Environments → dev**

| 종류 | 이름 |
|:--|:--|
| Secrets | `DISCORD_WEBHOOK_URL` (시험 채널) |

---

## 구조

```
main.py              그래프 조립
config.py            모델·도구·상수
state.py             그래프 상태와 리듀서
nodes/
  base.py            Node / LLMNode 공통 골격
  <노드>/
    node.py          노드 로직
    prompts.py       프롬프트와 ChatPromptTemplate
utils/
  storage.py         reports/ 읽고 쓰기
  discord.py         웹훅 발송 (2,000자 분할, 429 재시도, 채널 여러 개)
  text.py            인용 색인 만들기, 본문 정리
  trace.py           터미널 트레이스
```

프롬프트 조립용 빌더는 따로 안 만들었습니다. LangChain의 `ChatPromptTemplate`이 그 역할을 합니다. 노드 폴더는 문구와 템플릿 정의만 갖고, 변수 채우기와 모델 연결은 `template | model`이 합니다.

---

## 기술 스택

| 영역 | 사용 |
|:--|:--|
| 오케스트레이션 | LangGraph (StateGraph, ToolNode, 조건부 엣지, 커스텀 리듀서) |
| LLM | OpenAI 호환 엔드포인트 |
| 검색 | Tavily Search API |
| 관측 | LangSmith 트레이싱, 자체 콜백 핸들러 |
| 실행 | uv, GitHub Actions |

---

## 라이선스

MIT

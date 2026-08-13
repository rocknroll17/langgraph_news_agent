# 시장 브리핑 에이전트

매일 아침 미국·유럽·아시아 증시 뉴스를 수집해 **사실검증을 거친** 브리핑으로 정리하고 디스코드로 발송하는 LangGraph 파이프라인입니다.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green">
</p>

LLM은 OpenAI 호환 엔드포인트라면 무엇이든 연결됩니다. 이 저장소의 기본 구성은 로컬 llama.cpp에 올린 gemma4입니다.

---

## 설계 배경

소형 로컬 모델에 "검색 결과를 읽고 브리핑을 작성하라"는 요구를 한 번에 전달하면 세 가지가 동시에 무너집니다. 원문을 끝까지 읽지 않고, 수치의 소수점을 흘리며, 근거 없는 문장을 만들어냅니다.

이 프로젝트는 그 요구를 **한 노드가 한 가지 일만 하도록** 분해합니다. 검색 계획, 사실 추출, 글쓰기, 검증, 교정이 각각 독립된 노드이며 서로의 출력만 신뢰합니다.

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

| 노드 | 책임 | LLM |
|:--|:--|:-:|
| `planner` | 검색어를 한 번에 4~6개 발행. 답변은 작성하지 않음 | ● |
| `search` | `ToolNode`로 Tavily 검색을 병렬 실행 | |
| `synthesizer` | 검색 원문에서 사실만 추출하고 주장 간 인과·대조를 표기 | ● |
| `writer` | 사실 목록을 읽히는 글로 재구성. 검색 원문은 참조하지 않음 | ● |
| `checker` | 주장 단위로 분해해 원문 색인과 대조하고 판정만 수행 | ● |
| `reviser` | 판정에 따라 오류 구간만 수정하고 인용을 삽입 | ● |
| `reporter` | 파일 저장 및 디스코드 발송 | |
| `cleaner` | 다음 회차를 위한 상태 초기화 | |

---

## 사실검증

`writer`가 생성한 문장을 `checker`가 주장 단위로 분해해 검색 원문 색인과 대조합니다. 판정은 `SUPPORTED` / `CONTRADICTED` / `NOT_ENOUGH_INFO` 세 가지이며, `reviser`가 판정 결과에 따라 해당 구간만 수정합니다.

```
[checker] 주장 16건 — 근거있음 9 / 어긋남 1 / 근거없음 6
   ✗ 다우존스 0.04% 하락 53,770.27  →  색인값: 0.06% 하락 53,762.05
   ✗ 상하이 종합지수 0.50% 하락      →  색인값: 0.32% 상승
```

판정과 수정을 분리한 이유는 한 번의 호출로 두 작업을 요구하면 양쪽 품질이 함께 떨어지기 때문입니다. 사실검증 연구에서 확립된 **주장 분해 → 근거 인용 → 최소 수정** 순서를 따릅니다.

**발송 결과 예시**

> ### 오늘 한눈에
> 미국 증시는 AI 관련 기술주 강세에 힘입어 상승 마감했습니다. 7월 소비자물가지수가 예상을 밑돌며 연준의 금리 동결 기조가 재확인되었습니다.
>
> ### 미국 증시
> S&P 500은 0.3% 상승한 7,748.50으로 마감했으며, 나스닥 종합지수 역시 0.54% 올라 26,588.49를 기록했습니다([Zacks](https://example.com), [Reuters](https://example.com)). 다만 다우존스 산업평균지수는 0.06% 하락한 53,762.05로 마감해 지수 간 차별화가 나타났습니다([TS2](https://example.com)).

---

## 설계 노트

### 프롬프트가 아니라 코드로 강제하는 것

프롬프트로 요청해서는 지켜지지 않는 제약은 코드가 처리합니다.

| 문제 | 처리 |
|:--|:--|
| 모델이 "최대 6회" 제한을 초과한다 | `tool_calls[:MAX_CALLS]`로 절단 |
| 오래된 기사를 당일 기사처럼 인용한다 | Tavily `time_range="day"` 고정 |
| 모델이 `start_date`를 채워 API가 400을 반환한다 | `query`만 받는 래퍼 도구로 감쌈 |
| 출처 URL을 누락하거나 변형한다 | 검증 색인을 코드가 생성해 전달 |
| "없음"만 적힌 빈 섹션을 만든다 | 발행 직전 섹션 제목까지 제거 |

### 데이터는 시스템 프롬프트에 넣지 않는다

시스템 메시지에는 역할과 규칙만 담고 실제 데이터는 사용자 메시지로 전달합니다. 데이터를 시스템 프롬프트에 삽입하면 소형 모델이 이를 예시 자리로 해석해 "자료를 제공해 주세요"라고 되묻는 현상이 재현됩니다.

### 지난 브리핑을 참고 자료로 주입한다

`reports/`에 축적된 직전 브리핑을 `planner`에 **`HumanMessage`로** 전달합니다. `AIMessage`로 붙이면 모델이 자신의 이전 답변으로 인식해 검색 단계를 건너뜁니다.

이 구조 덕분에 이미 다룬 이슈는 후속 전개를 추적하고, 직전에 확보하지 못한 항목은 재조사 대상이 됩니다.

---

## 실행

### 설치

```bash
git clone https://github.com/rocknroll17/langgraph_news_agent.git
cd langgraph_news_agent
cp .env.example .env      # 키 입력
uv sync
```

### 명령

```bash
uv run python main.py             # 기본
TRACE=1 uv run python main.py     # 노드별 입출력 요약
TRACE=full uv run python main.py  # 프롬프트·응답 전문
```

`TRACE=1` 출력 예시

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

`.github/workflows/daily-briefing.yml`이 매일 10:00(KST)에 동작합니다. GitHub 러너가 해당 시각에만 기동해 실행 후 종료되므로 상시 서버가 필요하지 않습니다.

생성된 브리핑은 `reports/`에 커밋됩니다. 러너는 매 실행마다 새 인스턴스이므로, 다음 회차의 `planner`가 직전 브리핑을 읽으려면 저장소에 남아야 합니다.

### 환경 분리

| 환경 | 트리거 | 발송 채널 | `reports/` 커밋 |
|:--|:--|:--|:-:|
| `prod` | 스케줄 (매일 10:00 KST) | 운영 채널 | ● |
| `dev` | 수동 실행 기본값 | 시험 채널 | ○ |

`dev`는 `DISCORD_WEBHOOK_URL`만 별도로 보유하고 나머지 값은 저장소 설정을 상속합니다. 시험 실행 결과가 운영 채널로 발송되거나 저장소에 커밋되지 않습니다.

수동 실행은 **Actions → 시장 브리핑 → Run workflow**에서 환경을 선택합니다.

### 등록 값

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

## 프로젝트 구조

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
  storage.py         reports/ 입출력
  discord.py         웹훅 발송 (2,000자 분할, 429 재시도, 다중 채널)
  text.py            인용 색인 생성, 본문 정리
  trace.py           터미널 트레이스
```

프롬프트 조립은 별도 빌더를 구현하지 않고 LangChain의 `ChatPromptTemplate`을 공통 빌더로 사용합니다. 노드 디렉터리는 문구와 템플릿 정의만 보유하며, 변수 치환과 모델 연결은 `template | model`이 담당합니다.

---

## 기술 스택

| 영역 | 사용 |
|:--|:--|
| 오케스트레이션 | LangGraph (StateGraph, ToolNode, 조건부 엣지, 커스텀 리듀서) |
| LLM | OpenAI 호환 엔드포인트 (기본값: 로컬 llama.cpp / gemma4) |
| 검색 | Tavily Search API |
| 관측 | LangSmith 트레이싱, 자체 콜백 핸들러 |
| 실행 환경 | uv, GitHub Actions |

---

## 라이선스

MIT

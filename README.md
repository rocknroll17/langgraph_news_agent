<h1 align="center">Market Briefing Agent</h1>

<p align="center">
  Searches market news, drafts a briefing, strips out unsupported claims, and posts it to Discord.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-green"></a>
</p>

---

## Output

> ### Today at a glance
> US equities closed higher as AI-related tech stocks rallied. July CPI came in below expectations, strengthening expectations that the Fed will hold rates steady.
>
> ### US markets
> The S&P 500 rose 0.3% to close at 7,748.50, and the Nasdaq Composite gained 0.54% to 26,588.49 ([Zacks](https://example.com), [Reuters](https://example.com)). The Dow Jones Industrial Average, however, slipped 0.06% to 53,762.05, leaving the major indices split ([TS2](https://example.com)).

The citations are not something the LLM attached on its own. They are inserted only into sentences whose claims were matched against the retrieved source text.

## Quick start

```bash
git clone https://github.com/rocknroll17/langgraph_news_agent.git
cd langgraph_news_agent
cp .env.example .env      # fill in your keys
uv sync
uv run python main.py
```

Any OpenAI-compatible endpoint works. Point `OPENAI_BASE_URL` in `.env` at whatever you use.

Set `TRACE=1` to print, per node, the prompts that went in and the responses that came back.

---

## Why split it into nodes

Asking a model to "read these search results and write a briefing" in one shot does not work. With four to six raw articles filling tens of thousands of tokens, summarizing and writing at the same time makes it skim the tail of the source, misreport figures, and invent facts that were never retrieved. That is textbook **hallucination**, and it gets worse as the model gets smaller.

So each node does exactly one thing.

```mermaid
flowchart LR
    P[planner] -->|enough queries| S[search]
    P -.->|too few · retry| P
    P -.->|gave up| SY
    S --> SY[synthesizer]
    SY --> W[writer]
    W --> C[checker]
    C --> R[reviser]
    R --> RP[reporter]
    RP --> CL[cleaner]
    CL --> E([END])
```

| Node | Responsibility | LLM |
|:--|:--|:-:|
| `planner` | Emits 4–6 search queries in a single turn. Writes no prose | ● |
| `search` | Fans the tool calls out in parallel via `ToolNode` | |
| `synthesizer` | Extracts claims from raw results and tags causal / contrastive links | ● |
| `writer` | Drafts prose from the extracted claims only. Never sees raw results | ● |
| `checker` | Matches each claim against the source index. Judges only | ● |
| `reviser` | Applies minimal edits per verdict and inserts citations | ● |
| `reporter` | Saves to file and posts to Discord | |
| `cleaner` | Clears state with `RemoveMessage` | |

`synthesizer` is the only node that reads raw search output. Everything downstream runs on a lighter context.

---

## Grounding verification

`checker` **decomposes** the draft into individual claims and matches each one against an index built from the retrieved sources. Verdicts follow the three-way NLI convention and come back through a Pydantic-typed structured output.

| Verdict | Meaning | What `reviser` does |
|:--|:--|:--|
| `SUPPORTED` | The source backs the claim as written | Insert citation |
| `CONTRADICTED` | The source states a different value | Replace the figure, then cite |
| `NOT_ENOUGH_INFO` | No supporting evidence in the index | Leave as is, no citation |

```
[checker] 16 claims — supported 9 / contradicted 1 / unsupported 6
   ✗ Dow down 0.04% at 53,770.27  →  index says: down 0.06% at 53,762.05
   ✗ Shanghai Composite down 0.50%  →  index says: up 0.32%
```

Judging and revising are split because doing both in one call degrades both. The order is **decompose → quote evidence, then judge → minimal edit**.

_Why evidence comes before the verdict:_ reverse the order and the model fabricates evidence to fit the conclusion it already reached.

---

## Design decisions

### Guardrails belong in code, not in the prompt

| Problem | Handling |
|:--|:--|
| It exceeds "at most 6 calls" no matter what the prompt says | Truncate with `tool_calls[:MAX_CALLS]` |
| It cites stale articles as if they were today's | Pin Tavily to `time_range="day"` |
| It fills in `start_date` and the API returns 400 | Wrap the tool so it only accepts `query` |
| It drops or rewrites source URLs | Build the verification index in code and inject it |
| It emits empty sections containing only "none" | Strip the heading itself right before sending |

### Data does not go into the system prompt

The system message carries role and rules only; the actual data arrives as a `HumanMessage`.

_Why:_ data placed inside a system prompt gets read as a few-shot example slot, and the model replies asking you to provide the material.

### Yesterday's briefing is attached as reference

The previous briefing in `reports/` is attached to `planner` as a `HumanMessage`. Topics already covered get followed up on, and items that could not be confirmed get another pass.

_Why not `AIMessage`:_ the model treats it as its own prior answer and skips the search step.

---

## Scheduled runs

`.github/workflows/daily-briefing.yml` runs daily at 10:00 KST. The GitHub runner spins up only for that window, so nothing needs to stay online. Each briefing is committed to `reports/`, where the next run's `planner` picks it up.

| Environment | Trigger | Channel | Commits to `reports/` |
|:--|:--|:--|:-:|
| `prod` | Schedule (daily, 10:00 KST) | Production | ● |
| `dev` | Default for manual runs | Staging | ○ |

`dev` overrides only `DISCORD_WEBHOOK_URL` and inherits everything else from the repository. Test runs never reach the production channel or touch the repository.

Register `OPENAI_BASE_URL`, `LOCAL_MODEL`, and `LANGSMITH_PROJECT` as repository Variables, and `OPENAI_API_KEY`, `TAVILY_API_KEY`, `DISCORD_WEBHOOK_URL`, `LANGSMITH_API_KEY` as Secrets. The `dev` environment needs `DISCORD_WEBHOOK_URL` on its own.

---

## Layout

```
main.py              graph assembly
config.py            model, tools, constants
state.py             graph state and reducers
nodes/<node>/        node.py (logic) + prompts.py (ChatPromptTemplate)
utils/               file I/O, Discord delivery, citation index, tracing
```

There is no hand-rolled prompt builder. LangChain's `ChatPromptTemplate` fills that role: each node package holds only its wording and template, while variable substitution and model binding happen through `template | model`.

## License

[MIT](LICENSE)

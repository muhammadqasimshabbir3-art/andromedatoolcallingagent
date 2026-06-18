# Andromeda Agent

**A multi-tool LangGraph agent powered by Groq (Llama 3.1)**

Andromeda is an intelligent assistant that combines a **decision agent**, **dedicated tool nodes**, and a **Streamlit chat UI**. It understands natural-language requests and routes them to the right capability — scientific math, web search, local file search, PDF generation, and Gmail email — without manual tool selection.

| | |
|---|---|
| **Author** | Muhammad Qasim Shabbir |
| **Email** | [muhammadqasimshabbir3@gmail.com](mailto:muhammadqasimshabbir3@gmail.com) |
| **Version** | 0.1.0 |
| **License** | MIT |

---

## What Andromeda Does

Andromeda is built for **real multi-step workflows** in a single conversation. Ask it to introduce itself, solve a batch of engineering exam problems, generate a stylized PDF report, and email the results — it plans the steps and executes them in order.

For simpler requests, a **decision agent** analyzes your query and sends it directly to the correct graph node (calculator, file search, web search, email, or general chat).

### Core capabilities

| Capability | Description |
|------------|-------------|
| **Casio-style calculator** | Logs, natural log, trig (DEG mode), powers, factorials, complex numbers (iota), batch expression solving |
| **Web search** | DuckDuckGo via LangChain — no API key required; enable with the 🔍 toggle in the UI |
| **File search** | Find local files by name, extension (`.pdf`, `.csv`, etc.), or pattern |
| **PDF reports** | Generate styled text and table reports saved under `./reports/` |
| **Email (Gmail SMTP)** | Send results and attach generated PDFs via Gmail App Password |
| **Multi-task pipeline** | Introduce → calculate → create PDF → email in one message |
| **Streamlit UI** | Required user input, chat history, search toggle, example queries |
| **LangGraph Studio** | Visual debugging of all 10 graph nodes |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) `StateGraph` |
| LLM | Groq `llama-3.1-8b-instant` via `ChatGroq` |
| Tools | LangChain `@tool` decorators |
| Web search | `langchain-community` + `duckduckgo-search` |
| Math engine | SymPy |
| PDF generation | ReportLab |
| UI | Streamlit |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| API / Studio | LangGraph Server (`langgraph dev`) |

---

## Architecture

```
User (Streamlit UI)
        │
        ▼
  prepare_input ──► decision_agent
        │                │
        │    ┌───────────┼───────────┬────────────┬──────────────┐
        │    ▼           ▼           ▼            ▼              ▼
        │ execute_   run_        run_      run_web_      run_file_
        │ workflow   calculator  email     search        search
        │    │           │           │            │              │
        │    └───────────┴───────────┴────────────┴──────────────┘
        │                              │
        │                    call_model ⇄ tools
        │                    (PDF, email, calculator fallback)
        ▼
       END
```

### Decision agent routing

On each new user message, `decision_agent` (`task_planner.py`) chooses **one** path:

1. **Multi-task** → `execute_workflow` (2+ tasks: intro, math, PDF, email)
2. **Math + email** → `math_and_email`
3. **Math only** → `run_calculator`
4. **Email only** → `run_email`
5. **Web search** → `run_web_search` (only if 🔍 is enabled **and** the query needs live web info)
6. **File search** → `run_file_search`
7. **General chat** → `call_model` → `tools` loop

### Graph nodes (10)

| Node | Purpose |
|------|---------|
| `prepare_input` | Normalize `user_input` into messages |
| `decision_agent` | Plan tasks and set `agent_route` |
| `execute_workflow` | Multi-step: intro → math → PDF → email |
| `run_calculator` | Direct Casio calculator path |
| `run_email` | Send prior results via Gmail |
| `math_and_email` | Calculate then email |
| `run_web_search` | DuckDuckGo web search |
| `run_file_search` | Local filesystem search |
| `call_model` | Groq LLM with tool binding |
| `tools` | Execute LLM-selected tools |

Full diagrams and flows: **[AgentWorkflow.md](./AgentWorkflow.md)**

---

## Tools

| Tool | Graph path | When it runs |
|------|------------|--------------|
| `casio_calculator` | `run_calculator` | Math expressions detected |
| `solve_math_batch_tool` | `run_calculator` / `tools` | Multiple problems in one query |
| `web_search` | `run_web_search` | User enabled 🔍 + query needs internet |
| `search_files` | `run_file_search` | Find/list local files |
| `generate_pdf_report` | `execute_workflow` / `tools` | PDF report requested |
| `generate_table_report` | `tools` | Table data → PDF |
| `send_email` | `run_email` / `execute_workflow` / `tools` | Email intent detected |

---

## Prerequisites

- **Python** 3.11 or 3.12
- **[uv](https://github.com/astral-sh/uv)** (recommended) or pip
- **Groq API key** — [console.groq.com](https://console.groq.com/)
- **Gmail App Password** — only if you use the email feature ([Google Account → Security → App passwords](https://myaccount.google.com/apppasswords))

Web search requires **no additional API keys**.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/andromeda-agent.git
cd andromeda-agent

# Configure environment
cp .env.example .env
# Edit .env — at minimum set GROQ_API_KEY

# First-time setup (installs dependencies)
chmod +x setup.sh start.sh
./setup.sh
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | **Yes** | Groq API key for the LLM |
| `GMAIL_SMTP_USER` | For email | Your Gmail address |
| `GMAIL_APP_PASSWORD` | For email | 16-character Gmail App Password (quote if it contains spaces) |
| `GMAIL_DEFAULT_RECIPIENT` | For email | Default recipient for `send_email` |
| `LANGSMITH_API_KEY` | Optional | Enable LangSmith tracing |
| `LANGSMITH_PROJECT` | Optional | LangSmith project name (default: `new-agent`) |

**Example `.env`:**

```env
GROQ_API_KEY=gsk_your_key_here
GMAIL_SMTP_USER=your.email@gmail.com
GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
GMAIL_DEFAULT_RECIPIENT=your.email@gmail.com
```

---

## Running Andromeda

| Command | Description | URL |
|---------|-------------|-----|
| `./start.sh ui` | Streamlit chat interface | http://localhost:8501 |
| `./start.sh server` | LangGraph API + Studio | http://localhost:2024/studio |
| `./start.sh both` | UI and Studio together | Both URLs above |
| `./start.sh stop` | Stop running services | — |
| `uv run langgraph dev` | LangGraph dev server only | http://localhost:2024 |

### Streamlit UI

- **User input is required** — empty sends show an error
- **🔍 toggle** — enable web search; the decision agent searches only when your query needs live information
- **Example queries** — click sidebar buttons to pre-fill common requests
- **Chat history** — full conversation displayed in the main panel

---

## Example queries

| Query | Route |
|-------|-------|
| `What is log(1000) + sin(30)?` | `run_calculator` |
| `Find all CSV files in current directory` | `run_file_search` |
| `Search the web for Python best practices` | `run_web_search` (🔍 on) |
| `Email me a summary of today's findings` | `run_email` |
| `Generate a PDF report about AI and email it to me` | `call_model` → `tools` |
| Multi-step exam query (intro + 11 math problems + PDF + email) | `execute_workflow` |

**Multi-task example:**

```
Introduce yourself, then calculate:
log(1000) + ln(E^5), sin(73.5) * cos(41.2) + tan(12.7), (3 + 4i)^7
Create a stylized PDF with questions and answers, then email it to me.
```

---

## Project structure

```
andromeda/
├── README.md                    # This file
├── AgentWorkflow.md             # Graph architecture and flows
├── LICENSE                      # MIT
├── pyproject.toml               # Dependencies and package metadata
├── langgraph.json               # LangGraph Server configuration
├── .env.example                 # Environment template
│
├── docs/
│   ├── GITHUB_SETUP.md          # Publish to GitHub
│   └── PROJECT_STRUCTURE.md     # Detailed layout
│
├── scripts/
│   └── services.sh              # Port/process helpers
│
├── setup.sh                     # First-time install
├── start.sh                     # Run UI / server / both
├── streamlit_ui.py              # Chat web interface
│
├── src/agent/
│   ├── graph.py                 # LangGraph definition (nodes, edges)
│   ├── task_planner.py          # Decision agent — task planning
│   ├── routing.py               # Intent detection and fallbacks
│   ├── workflow_executor.py     # Multi-step pipeline executor
│   ├── async_utils.py           # Async wrappers for blocking I/O
│   └── custom_tools/
│       ├── calculator_tools.py  # Casio-style scientific calculator
│       ├── web_search_tools.py  # DuckDuckGo web search
│       ├── file_search_tools.py # Local file search
│       ├── email_tools.py       # Gmail SMTP
│       └── pdf_generator.py     # ReportLab PDF reports
│
├── tests/
│   ├── unit_tests/              # Unit tests (34+ tests)
│   └── integration_tests/       # Graph integration tests
│
└── reports/                     # Generated PDFs (gitignored)
```

---

## Development

```bash
# Run unit tests
uv run pytest tests/unit_tests/ -v

# Verify graph loads and list nodes
uv run python -c "from agent import graph; print(list(graph.get_graph().nodes.keys()))"

# Lint (optional)
uv run ruff check src/
```

Expected graph nodes:

```
prepare_input, decision_agent, execute_workflow, run_calculator,
run_email, math_and_email, run_web_search, run_file_search,
call_model, tools
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [AgentWorkflow.md](./AgentWorkflow.md) | Mermaid diagrams, routing logic, example flows |
| [SETUP_GUIDE.md](./SETUP_GUIDE.md) | Detailed setup and troubleshooting |
| [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md) | Full directory layout |
| [docs/GITHUB_SETUP.md](./docs/GITHUB_SETUP.md) | How to publish to GitHub |

---

## Publish to GitHub

Suggested repository name: **`andromeda-agent`**

```bash
git init
git add .
git commit -m "Initial commit: Andromeda multi-tool LangGraph agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/andromeda-agent.git
git push -u origin main
```

Step-by-step guide: **[docs/GITHUB_SETUP.md](./docs/GITHUB_SETUP.md)**

---

## Author

**Muhammad Qasim Shabbir**  
Email: [muhammadqasimshabbir3@gmail.com](mailto:muhammadqasimshabbir3@gmail.com)

---

## License

This project is licensed under the **MIT License** — see [LICENSE](./LICENSE).

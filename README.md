# Andromeda Agent

**A multi-tool LangGraph assistant powered by Groq, Gmail, web/file tools, PDF analysis, and browser-based UIs.**

Andromeda is an intelligent workflow agent that routes natural-language requests to the right capability: scientific calculation, web search, local file search, live location lookup, PDF generation, uploaded-PDF analysis, Gmail inbox automation, and general conversation.

| | |
|---|---|
| **Author** | Muhammad Qasim Shabbir |
| **Email** | [muhammadqasimshabbir3@gmail.com](mailto:muhammadqasimshabbir3@gmail.com) |
| **Version** | 0.1.0 |
| **License** | MIT |

---

## What Andromeda Does

Andromeda is built for real multi-step workflows. You can ask it to calculate a batch of engineering expressions, create a PDF report, analyze an uploaded PDF, search the web, find local files, check your location, or process unread Gmail messages.

A decision agent analyzes each message and chooses one route through the LangGraph graph. Simple requests go directly to a dedicated node. Broader conversations use the Groq model with bound tools.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **Scientific calculator** | Logs, natural log, trig in degree mode, powers, factorials, complex numbers, and batch expression solving |
| **Web search** | DuckDuckGo/DDGS search through LangChain community tools; no separate search API key required |
| **File search** | Find files by name, extension, directory, or pattern |
| **PDF reports** | Generate styled text and table reports with ReportLab |
| **PDF analysis** | Upload PDFs, extract text with `pypdf`, build an in-memory Chroma index, summarize, and answer PDF-grounded questions |
| **Gmail inbox automation** | OAuth Gmail API flow to read unread messages, generate replies with Groq or Ollama, reply in-thread, and mark messages as read |
| **Live location** | Browser coordinates plus OpenStreetMap Nominatim/Overpass lookups for address and nearby places |
| **Conversation memory** | Streamlit and React flows send message history/state so follow-up requests can reference prior answers |
| **Multi-task routing** | Plan and execute multi-step requests such as calculate -> generate PDF -> email/process inbox |
| **LangGraph Studio** | Visual debugging through `langgraph dev` |
| **UIs** | Streamlit chat UI and a Vite/React dashboard frontend |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph `StateGraph` |
| LLM | Groq through `langchain-groq` |
| Tools | LangChain `@tool` decorators |
| Web search | `langchain-community`, `duckduckgo-search`, `ddgs` |
| Math | SymPy |
| PDF generation | ReportLab |
| PDF analysis | `pypdf` + in-memory ChromaDB |
| Gmail | Gmail API OAuth client libraries; legacy SMTP helper still exists in `email_tools.py` |
| Location | OpenStreetMap Nominatim + Overpass API |
| Python UI | Streamlit |
| Frontend UI | React 19 + Vite + TypeScript + LangGraph SDK |
| Package manager | `uv` |
| Deployment | Docker/LangGraph API, Railway config, Vercel frontend config |

---

## Architecture

```text
User
  |
  v
Streamlit UI or React frontend
  |
  v
prepare_input -> decision_agent
                 |
                 +-> execute_workflow
                 +-> run_calculator
                 +-> run_email / run_gmail_inbox
                 +-> math_and_email
                 +-> run_web_search
                 +-> run_file_search
                 +-> run_location
                 +-> run_pdf_analysis
                 +-> call_model -> tools -> call_model
```

### Graph Nodes

The compiled graph currently contains these 13 nodes:

| Node | Purpose |
|------|---------|
| `prepare_input` | Normalize `user_input` or existing `messages` into graph messages |
| `decision_agent` | Choose an execution route and summarize the task plan |
| `execute_workflow` | Run multi-step planned workflows |
| `run_calculator` | Direct calculator path for math-only requests |
| `run_email` | Maps email intent to the Gmail inbox flow |
| `run_gmail_inbox` | Process unread Gmail messages through OAuth + Groq/Ollama |
| `math_and_email` | Calculate first, then run the Gmail inbox action |
| `run_web_search` | Run web search when the web toggle/state allows it |
| `run_file_search` | Search local files |
| `run_location` | Reverse-geocode browser coordinates and find nearby places |
| `run_pdf_analysis` | Summarize or answer questions against an uploaded PDF |
| `call_model` | General Groq chat path with tool binding |
| `tools` | Execute model-selected tools and loop back to `call_model` |

More flow detail is in [AgentWorkflow.md](./AgentWorkflow.md).

---

## Repository Layout

```text
.
├── README.md
├── AgentWorkflow.md
├── Dockerfile
├── langgraph.json
├── pyproject.toml
├── setup.sh
├── start.sh
├── streamlit_ui.py
├── railway.json
├── vercel.json
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── .env.example
│   └── src/
│       ├── App.tsx
│       ├── config.ts
│       ├── components/
│       ├── hooks/
│       └── lib/
├── scripts/
│   └── services.sh
├── src/
│   ├── gmail_agent.py
│   └── agent/
│       ├── graph.py
│       ├── routing.py
│       ├── task_planner.py
│       ├── workflow_executor.py
│       ├── pdf_analysis.py
│       └── custom_tools/
│           ├── calculator_tools.py
│           ├── email_tools.py
│           ├── file_search_tools.py
│           ├── gmail_inbox_tools.py
│           ├── location_tools.py
│           ├── pdf_generator.py
│           └── web_search_tools.py
└── tests/
    ├── unit_tests/
    └── integration_tests/
```

---

## Prerequisites

- Python 3.11 or 3.12
- `uv`
- Groq API key for the main agent
- Node.js and npm for the React frontend
- Gmail OAuth Desktop credentials if you want Gmail inbox automation
- Ollama only if you want local fallback replies for Gmail automation

Web search does not need a separate API key. Location lookup uses public OpenStreetMap services and can be customized with `OSM_USER_AGENT`.

---

## Environment Variables

Create a root `.env` file before running `setup.sh` or `start.sh`.

```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama3-8b-8192

# Optional LangSmith tracing/auth
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=new-agent

# Gmail OAuth inbox automation
GOOGLE_CLIENT_SECRETS=client_secret.json
GMAIL_TOKEN_FILE=gmail_token.json
GMAIL_SCOPES=https://www.googleapis.com/auth/gmail.modify
GMAIL_USER_ID=me
GMAIL_INBOX_QUERY=is:unread in:inbox
GMAIL_PROCESS_LIMIT=0

# Ollama fallback for Gmail replies
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=120
OLLAMA_MAX_TOKENS=512

# Optional legacy SMTP helper
GMAIL_SMTP_USER=your.email@gmail.com
GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
GMAIL_DEFAULT_RECIPIENT=your.email@gmail.com

# Optional location service identity
OSM_USER_AGENT=AndromedaAgent/0.1 (your-contact@example.com)
LOG_LEVEL=INFO
```

### Frontend Environment

For the React frontend, copy [frontend/.env.example](./frontend/.env.example) to `frontend/.env` if you need custom values.

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_LANGGRAPH_API_URL` | `/api` | LangGraph API URL or Vite/Vercel proxy path |
| `VITE_LANGGRAPH_ASSISTANT_ID` | `agent` | Must match `langgraph.json` graph key |
| `VITE_LANGSMITH_API_KEY` | empty | Optional key for authenticated deployments |
| `VITE_DEFAULT_USER_INPUT` | calculator example | Default form input |
| `VITE_DEFAULT_WEB_SEARCH` | `false` | Default search toggle value |

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/andromeda-agent.git
cd andromeda-agent

# Create and edit .env first.
nano .env

chmod +x setup.sh start.sh
./setup.sh
```

If you prefer manual installation:

```bash
uv venv .venv
uv sync
```

---

## Running The Project

### Streamlit UI

```bash
./start.sh ui
```

Open `http://localhost:8501`.

The Streamlit UI includes chat history, web-search toggle, PDF upload/analysis, browser geolocation fallback, environment status, and example prompts.

### LangGraph Server And Studio

```bash
./start.sh server
```

By default `start.sh server` runs `langgraph dev` on port `2024` with a tunnel for LangGraph Studio.

You can also run the local server directly:

```bash
uv run langgraph dev --port 2024
```

### Streamlit + LangGraph Server

```bash
./start.sh both
```

### React Frontend

Start the LangGraph server first, then run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The React app provides a dashboard-style interface with connection diagnostics, run controls, workflow progress, activity log, result display, persisted run/session state, optional PDF state, and frontend defaults from Vite environment variables.

---

## Gmail OAuth Inbox Automation

This project can read unread Gmail messages, draft replies with Groq or Ollama, send replies in the same thread, and mark messages as read.

Setup:

1. Enable the Gmail API in Google Cloud Console.
2. Create an OAuth Client ID with application type `Desktop app`.
3. Download the JSON credentials file.
4. Set `GOOGLE_CLIENT_SECRETS` in `.env` to that JSON file path.
5. Set `GMAIL_TOKEN_FILE` to where the OAuth token should be cached.
6. Run the agent once to complete browser consent.

```bash
uv run python src/gmail_agent.py
uv run python src/gmail_agent.py --limit 5
```

You can also trigger the flow through chat with prompts like:

```text
Process my unread Gmail inbox messages
Read my 5 unread emails
Reply to unread Gmail messages
```

Keep OAuth secrets and token files out of version control.

---

## Example Prompts

| Prompt | Expected route |
|--------|----------------|
| `What is log(1000) + sin(30)?` | `run_calculator` |
| `Find all CSV files in current directory` | `run_file_search` |
| `Search the web for Python best practices` | `run_web_search` when web search is enabled |
| `Where am I?` | `run_location` when coordinates are available |
| `Find nearby restaurants` | `run_location` |
| `Summarize this uploaded PDF` | `run_pdf_analysis` when PDF data is provided |
| `Process my unread Gmail inbox messages` | `run_gmail_inbox` |
| `Generate a PDF report about AI` | `call_model` -> `tools` |
| `Introduce yourself, calculate these expressions, create a PDF report` | `execute_workflow` |

---

## Development

```bash
# Unit tests
uv run pytest tests/unit_tests/ -v

# Integration tests
uv run pytest tests/integration_tests/ -v

# All tests
uv run pytest

# Verify graph imports
uv run python -c "from agent import graph; print(list(graph.get_graph().nodes.keys()))"

# Lint
uv run ruff check src tests

# React build
cd frontend
npm run build
```

Expected graph nodes:

```text
prepare_input, decision_agent, execute_workflow, run_calculator,
run_email, run_gmail_inbox, math_and_email, run_web_search, run_file_search,
run_location, run_pdf_analysis, call_model, tools
```

---

## Deployment Notes

- [langgraph.json](./langgraph.json) registers the graph as `agent` and configures permissive CORS for local, Studio, and deployed frontend use.
- [Dockerfile](./Dockerfile) is based on `langchain/langgraph-api:3.12` and exposes the LangGraph API service.
- [railway.json](./railway.json) configures Railway to build from the Dockerfile.
- [vercel.json](./vercel.json) builds the React frontend from `frontend/` and serves the Vite output.
- The frontend defaults to `/api`; add a rewrite/proxy to your backend if deploying separately.

---

## Security Notes

- Do not commit `.env`, Gmail OAuth client secrets, Gmail token files, or app passwords.
- Use a Gmail App Password only for the legacy SMTP helper.
- Use Gmail OAuth for inbox reading and in-thread replies.
- OpenStreetMap services are public; set a meaningful `OSM_USER_AGENT` for production use.
- Uploaded PDF indexes are in-memory and process-local.

---

## License

This project is licensed under the **MIT License**. See [LICENSE](./LICENSE).

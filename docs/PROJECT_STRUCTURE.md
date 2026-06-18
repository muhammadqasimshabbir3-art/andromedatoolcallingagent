# Project structure

```
andromeda/
├── README.md                 # Overview and quick start
├── AgentWorkflow.md          # Graph architecture and tool flows
├── LICENSE                   # MIT license
├── pyproject.toml            # Python package and dependencies
├── langgraph.json            # LangGraph Server config
├── .env.example              # Environment template (copy to .env)
├── .gitignore
│
├── docs/
│   ├── GITHUB_SETUP.md       # How to publish to GitHub
│   └── PROJECT_STRUCTURE.md  # This file
│
├── scripts/
│   └── services.sh           # Port/process helpers for start.sh
│
├── setup.sh                  # First-time install
├── start.sh                  # Run UI and/or LangGraph server
├── streamlit_ui.py           # Chat web interface
│
├── src/agent/                # Agent package
│   ├── graph.py              # LangGraph definition (nodes, edges, routing)
│   ├── task_planner.py       # Decision agent: plan tasks from user query
│   ├── routing.py            # Intent detection and fallback responses
│   ├── workflow_executor.py  # Multi-step pipeline (intro → math → PDF → email)
│   ├── async_utils.py        # Async wrappers for blocking I/O
│   └── custom_tools/         # LangChain @tool implementations
│       ├── calculator_tools.py
│       ├── web_search_tools.py   # DuckDuckGo (no API key)
│       ├── file_search_tools.py
│       ├── email_tools.py
│       └── pdf_generator.py
│
├── tests/
│   ├── unit_tests/           # Fast unit tests
│   └── integration_tests/    # Graph integration tests
│
└── reports/                  # Generated PDFs (gitignored)
```

## Graph nodes and tools

| Graph node | Tool / action | When it runs |
|------------|---------------|--------------|
| `run_calculator` | Casio calculator | Math detected |
| `run_email` | Gmail SMTP | Email intent |
| `math_and_email` | Calculator + email | Both intents |
| `run_web_search` | DuckDuckGo web search | User enabled 🔍 + query needs web |
| `run_file_search` | Local file search | File-find intent |
| `execute_workflow` | Multi-step pipeline | 2+ workflow tasks |
| `call_model` → `tools` | PDF, email, calculator (LLM-chosen) | General chat / fallback |

Dedicated nodes handle calculator, web search, and file search directly. The `tools` node is only used by the LLM loop for PDF generation, email, and calculator fallback.

# 🚀 Andromeda Agent - Setup & Run Guide

> **Workflow diagrams:** see [AgentWorkflow.md](./AgentWorkflow.md)  
> **Quick start (after setup):** `./start.sh ui`

## Quick Start

### First time — run setup

```bash
cp .env.example .env   # add GROQ_API_KEY and optional Gmail keys
chmod +x setup.sh start.sh
./setup.sh
```

### Every day — start the agent

```bash
./start.sh ui       # Streamlit chat UI (recommended)
./start.sh server   # LangGraph Studio debugger
./start.sh both     # Both services
```

The setup script will:
1. ✅ Check environment variables (.env)
2. ✅ Verify Python and dependencies
3. ✅ Install/sync dependencies with `uv`
4. ✅ Check LangGraph CLI
5. ✅ Verify all imports
6. ✅ Prompt you to choose a service to run

---

## What Each Option Does

### `./start.sh ui` — Streamlit Web UI (recommended)

```bash
./start.sh ui
```

**Best for:**
- User-friendly interface
- Interactive chat
- Seeing tool outputs
- Daily use and demos

**URL:** http://localhost:8501

---

### `./start.sh server` — LangGraph Server

```bash
./start.sh server
```

**Best for:**
- Debugging with LangGraph Studio
- Visual graph inspection
- API access

**URLs:**
- Server: http://localhost:2024
- Studio: http://localhost:2024/studio

---

### `./start.sh both` — Both services

Runs LangGraph Server and Streamlit UI together.

---

### `./setup.sh` — First-time setup + menu

Same as before; use when dependencies are not installed yet.

### Option 1: LangGraph Server (from setup menu)
```bash
langgraph dev
```

**Best for:**
- Debugging with LangGraph Studio
- Visual debugging IDE
- Testing graph logic
- Development

**URLs:**
- Server: http://localhost:2024
- Studio: http://localhost:2024/studio

---

### Option 2: Streamlit Web UI
```bash
streamlit run streamlit_ui.py
```

**Best for:**
- User-friendly interface
- Interactive chat
- Seeing tool outputs
- Production use

**URL:**
- http://localhost:8501

---

### Option 3: Both Services
Runs both LangGraph Server and Streamlit UI simultaneously

**Use this for:**
- Full-stack development
- Testing UI while debugging graph
- Comparing both interfaces

---

## Prerequisites

Make sure you have:
1. Python 3.11+ installed
2. `.env` file created with API keys
3. `uv` package manager (installed automatically)

---

## Setup Checklist

Before running the script:

```bash
# 1. Create .env from template
cp .env.example .env

# 2. Add your API keys to .env
nano .env
# Add:
# GROQ_API_KEY=gsk_YOUR_KEY
# GMAIL_SMTP_USER=your.email@gmail.com
# GMAIL_APP_PASSWORD=your-app-password
# GMAIL_DEFAULT_RECIPIENT=your.email@gmail.com
# LANGSMITH_API_KEY=lsv_YOUR_KEY

# 3. Run setup (first time)
chmod +x setup.sh start.sh
./setup.sh

# 4. Start agent (after setup)
./start.sh ui
```

---

## What the Script Does

### 1. Environment Validation
- Checks if `.env` file exists
- Loads environment variables
- Verifies GROQ_API_KEY is set

### 2. Dependency Management
- Checks for Python 3
- Verifies or installs `uv` package manager
- Creates virtual environment if needed
- Syncs dependencies

### 3. LangGraph CLI Setup
- Checks for `langgraph` command
- Installs if needed

### 4. Verification
- Tests all imports
- Verifies ChatGroq integration
- Checks custom tools availability

### 5. Service Selection
- Prompts user to choose service
- Starts selected service(s)

---

## Services Explained

### LangGraph Server
The LangGraph Server provides a REST API and visual debugging interface.

**Features:**
- ✅ Visual graph debugger
- ✅ State inspection
- ✅ Thread management
- ✅ Past state editing/replay
- ✅ LangSmith integration

**Start:**
```bash
langgraph dev
```

**Access:** http://localhost:2024/studio

---

### Streamlit Web UI
A web interface for interacting with the agent.

**Features:**
- ✅ Chat interface
- ✅ Tool information display
- ✅ API status checking
- ✅ Interactive examples
- ✅ Statistics

**Start:**
```bash
streamlit run streamlit_ui.py
```

**Access:** http://localhost:8501

---

## Troubleshooting

### "Python version not supported" (LangGraph)
LangGraph requires Python 3.11+. This project sets `python_version` to 3.12 in `langgraph.json`.
```bash
python3 --version   # should be 3.11 or 3.12
```

### "Address already in use" (port 2024 or 8501)
A previous LangGraph or Streamlit process is still running.
```bash
./start.sh stop
./start.sh server    # or ./start.sh both
```

Or manually:
```bash
fuser -k 2024/tcp
fuser -k 8501/tcp
```

### "streamlit: command not found"
Use the project scripts (they run via `uv run`):
```bash
./start.sh ui
# or
uv run streamlit run streamlit_ui.py
```

### "GROQ_API_KEY not set"
```bash
# Create .env file
cp .env.example .env

# Add your key
nano .env
# GROQ_API_KEY=gsk_YOUR_KEY
```

### "uv not found"
```bash
# Install uv
pip install uv
```

### "Python 3 not found"
```bash
# Install Python 3.10+
# On macOS:
brew install python@3.11

# On Ubuntu/Debian:
sudo apt-get install python3.11 python3.11-venv

# On Windows:
# Download from python.org
```

### "LangGraph CLI not found"
```bash
# Install manually
pip install langgraph-cli[inmem]
```

---

## Advanced Usage

### Manual LangGraph Server
```bash
# Start development server
langgraph dev

# OR with custom port
langgraph dev --port 3000
```

### Manual Streamlit UI
```bash
streamlit run streamlit_ui.py --logger.level=info
```

### Run Both (Manual)
```bash
# Terminal 1
langgraph dev

# Terminal 2
streamlit run streamlit_ui.py
```

---

## Features Included

The Andromeda Agent includes:

- 🧮 **Scientific Calculator** — Casio-style logs, trig, complex/iota
- 🌐 **Web Search** — DuckDuckGo integration
- 🗂️ **File Search** — Local file discovery
- 📓 **Kaggle Notebooks** — Search and retrieve notebooks
- 📄 **PDF Generation** — Styled PDF reports
- 📧 **Email Reports** — Gmail SMTP with PDF attachments
- 💬 **Natural Chat** — Conversational AI
- 🔧 **Tool Calling** — Automatic tool selection

See [AgentWorkflow.md](./AgentWorkflow.md) for workflow diagrams.

---

## Environment Variables

### Required
- `GROQ_API_KEY` - Your Groq API key from https://console.groq.com

### For email tool
- `GMAIL_SMTP_USER` - Gmail address used to send
- `GMAIL_APP_PASSWORD` - Gmail app password (not login password)
- `GMAIL_DEFAULT_RECIPIENT` - Default recipient when not specified

### Optional
- `LANGSMITH_API_KEY` - LangSmith tracing
- `LANGSMITH_PROJECT` - Project name (default: new-agent)

---

## Project Structure

```
andromeda/
├── AgentWorkflow.md ............. Workflow diagrams and run guide
├── start.sh ..................... Quick start (ui / server / both)
├── setup.sh ..................... First-time setup script
├── .env ......................... Your API keys (local only)
├── src/agent/
│   ├── graph.py ................ Main agent graph
│   └── custom_tools/ ........... Calculator, email, search, PDF, Kaggle
├── streamlit_ui.py ............. Web interface
├── README.md ................... Project overview
└── pyproject.toml .............. Dependencies
```

---

## Commands Summary

```bash
# First-time setup
./setup.sh

# Quick start (after setup)
./start.sh ui          # Streamlit chat
./start.sh server      # LangGraph Studio
./start.sh both        # Both

# Manual alternatives
langgraph dev
streamlit run streamlit_ui.py

# Verify dependencies
uv run python -c "from agent import graph; print('✅ Ready!')"
```

---

## Support

For issues:
1. Check API keys in `.env`
2. Verify Python version: `python3 --version`
3. Check dependencies: `uv sync`
4. Review logs in the console

---

**Happy coding! 🚀**


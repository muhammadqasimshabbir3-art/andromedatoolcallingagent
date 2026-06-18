# Publish Andromeda Agent to GitHub

## Suggested repository names

| Name | Why |
|------|-----|
| **`andromeda-agent`** | Short, clear, matches the project (recommended) |
| `langgraph-andromeda` | Highlights LangGraph stack |
| `groq-multi-tool-agent` | Highlights Groq + multi-tool design |
| `andromeda-langgraph-agent` | Descriptive for portfolio searches |

## One-time setup

### 1. Create the repo on GitHub

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `andromeda-agent`
3. Description: *Multi-tool LangGraph agent with calculator, web search, file search, PDF, and email*
4. Choose **Public** or **Private**
5. Do **not** add README, `.gitignore`, or license (this project already has them)
6. Click **Create repository**

### 2. Initialize git locally

From the project root:

```bash
cd /path/to/andromeda

# Initialize repository
git init

# Stage files (.env and .venv are already in .gitignore)
git add .

# First commit
git commit -m "Initial commit: Andromeda multi-tool LangGraph agent"

# Rename default branch (optional, GitHub standard)
git branch -M main

# Add your GitHub remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/andromeda-agent.git

# Push
git push -u origin main
```

### 3. Using SSH instead of HTTPS

```bash
git remote add origin git@github.com:YOUR_USERNAME/andromeda-agent.git
git push -u origin main
```

### 4. Using GitHub CLI (`gh`)

```bash
gh auth login
gh repo create andromeda-agent --public --source=. --remote=origin --push
```

## What gets committed

Included:

- Source code (`src/agent/`)
- Tests (`tests/`)
- Docs (`README.md`, `AgentWorkflow.md`, `docs/`)
- Scripts (`setup.sh`, `start.sh`, `scripts/`)
- Config templates (`.env.example`, `pyproject.toml`, `langgraph.json`)

Excluded (via `.gitignore`):

- `.env` (secrets)
- `.venv/` (virtual environment)
- `reports/` (generated PDFs)
- `__pycache__/`, `.pytest_cache/`
- `.langgraph_api/`

## After pushing

1. Copy `.env.example` → `.env` on any new machine (never commit `.env`)
2. Run `./setup.sh` then `./start.sh ui`
3. Add a repo description and topics on GitHub: `langgraph`, `langchain`, `groq`, `streamlit`, `ai-agent`

## Clone on another machine

```bash
git clone https://github.com/YOUR_USERNAME/andromeda-agent.git
cd andromeda-agent
cp .env.example .env
# Edit .env with your GROQ_API_KEY
chmod +x setup.sh start.sh
./setup.sh
./start.sh ui
```

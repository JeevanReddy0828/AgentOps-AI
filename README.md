# AgentOps AI - Intelligent IT Operations Platform

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange.svg)](https://www.anthropic.com/)
[![Tests](https://img.shields.io/badge/Tests-213_passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent IT Operations platform powered by multi-agent orchestration using Claude AI and LangGraph. The system automatically triages, resolves, and manages IT support tickets through specialized AI agents with a React dashboard.

---

## Features

- **Multi-Agent Architecture** — Triage, Resolution, and Compliance agents coordinated by a LangGraph state machine
- **AI Chat Assistant** — Claude-powered conversational support that troubleshoots before creating tickets
- **Dynamic Ticket Management** — Real-time ticket list with auto-refresh, status tracking, and resolution summaries
- **RAG Knowledge Base** — ChromaDB-backed context retrieval to ground agent responses
- **Automated Remediation** — Password resets, VPN config pushes, account unlocks, software installs
- **Compliance Gating** — Every tool execution validated against security rules before running
- **Local Cache** — All model weights and vector DB files stored inside the project folder
- **213 Tests** — Unit + edge case coverage across agents, API, security, and orchestrator

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│              Dashboard  |  Tickets  |  Chat                     │
│         (Vite + Tailwind + recharts + lucide-react)             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API (:8000)
┌──────────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                            │
│   /api/v1/chat   /api/v1/tickets   /api/v1/analytics/dashboard  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                  LangGraph Orchestrator                         │
│                                                                 │
│  START → TRIAGE → [decision]                                    │
│                   ├─ auto_resolve   → RESOLVE → FINALIZE        │
│                   ├─ agent_resolution → COMPLIANCE → RESOLVE    │
│                   ├─ human_escalation → ESCALATE → FINALIZE     │
│                   └─ information_request → FINALIZE             │
├──────────────┬──────────────┬──────────────────────────────────┤
│  TriageAgent │ResolutionAgent│   ComplianceAgent               │
│  (classify + │ (plan + tools)│   (rule engine +                │
│   route)     │               │    LLM validation)              │
└──────────────┴──────────────┴──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│              RAG Pipeline  +  Remediation Engine                │
│         ChromaDB (local)   sentence-transformers (local)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com/)

### 1. Clone

```bash
git clone https://github.com/yourusername/agentic-it-ops.git
cd agentic-it-ops
```

### 2. Backend

```powershell
# Windows PowerShell
python -m venv venv
venv\Scripts\Activate
pip install -r requirements.txt
pip install -e .
```

```bash
# Mac / Linux
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. Environment

Copy `.env` and add your API key:

```env
ANTHROPIC_API_KEY=your-api-key-here

# All cache files stay inside the project (no global ~/.cache writes)
HF_HOME=./.cache
SENTENCE_TRANSFORMERS_HOME=./.cache/sentence-transformers
```

### 5. Run

**Terminal 1 — Backend:**
```powershell
venv\Scripts\Activate
uvicorn src.api.main:app --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### 6. Open

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Readiness | http://localhost:8000/ready |

---

## Project Structure

```
agentic-it-ops/
├── src/
│   ├── agents/
│   │   ├── base_agent.py          # Claude client, rate limiting, tool registry, compliance gating
│   │   ├── triage_agent.py        # Keyword + LLM classification, routing decision
│   │   ├── resolution_agent.py    # Multi-step plan generation + tool execution
│   │   └── compliance_agent.py    # Rule engine + LLM policy validation
│   ├── workflows/
│   │   └── orchestrator.py        # LangGraph state machine, ticket storage, analytics
│   ├── tools/
│   │   └── remediation.py         # IT actions: password reset, VPN push, software install
│   ├── rag/
│   │   ├── knowledge_base.py      # ChromaDB collections, sentence-transformers embeddings
│   │   └── retriever.py           # Context retrieval with reranking
│   ├── api/
│   │   └── main.py                # FastAPI app, chat endpoint, ticket CRUD
│   ├── models/
│   │   └── ticket.py              # Pydantic models: Ticket, ActionResult, AgentState
│   └── utils/
│       ├── rate_limiter.py        # Sliding window RPM + TPM limiter with async lock
│       ├── security.py            # sanitize_input, mask_sensitive_data, RBAC
│       └── observability.py       # Prometheus metrics (optional), structured logging
├── frontend/
│   ├── AgentOpsDashboard.jsx      # Main dashboard: metrics, charts, chat, tickets
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── vite.config.js             # Port 5173, proxy /api → :8000
│   ├── tailwind.config.js
│   └── package.json
├── tests/
│   ├── test_agents.py             # 49 unit tests — agents, compliance, rate limiter, API
│   └── test_edge_cases.py         # 164 edge case tests — boundaries, XSS, injection, fallbacks
├── conftest.py                    # Sets ANTHROPIC_API_KEY=test-key for test runs
├── pytest.ini                     # asyncio_mode=auto, testpaths=tests
├── requirements.txt
└── .env                           # API key + local cache paths (never committed)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Chat with AI assistant (maintains conversation history) |
| GET | `/api/v1/tickets` | List all tickets |
| POST | `/api/v1/tickets` | Create a ticket (triggers background agent workflow) |
| GET | `/api/v1/tickets/{id}` | Get ticket details |
| GET | `/api/v1/tickets/{id}/status` | Get resolution status and actions taken |
| POST | `/api/v1/tickets/{id}/resolve` | Manually re-trigger resolution |
| GET | `/api/v1/analytics/dashboard` | Metrics: totals, rates, categories |
| GET | `/api/v1/analytics/trends` | Ticket volume over time |
| GET | `/api/v1/analytics/agents` | Agent performance stats |
| GET | `/api/v1/knowledge/search?query=` | Search knowledge base |
| GET | `/health` | Health check |
| GET | `/ready` | Readiness — confirms orchestrator + Claude client live |
| GET | `/metrics` | Prometheus metrics (if prometheus_client installed) |

---

## Chat Flow

The assistant troubleshoots before creating a ticket:

```
User:      "locked out of my account"
Assistant: "Let's get you back in. Try these steps:
            1. Go to the login page and click Forgot Password.
            2. Check your email for a reset link.
            3. If no email in 5 minutes, check spam.
            Did any of those work?"

User:      "none of them worked"
Assistant: "Understood. I can create a support ticket for our IT team
            to investigate. Would you like me to do that?"

User:      "yes please"
Assistant: "Support ticket INCXXXXXX has been created.
            Issue: Password/Login Issue
            Category: Access | Priority: Medium
            Our IT team will review it shortly."
```

Tickets appear instantly in the Tickets tab with auto-refresh every 10 seconds.

---

## Agent Details

### TriageAgent
- Keyword scoring across 5 categories × 9 priority levels
- LLM fallback via Claude for ambiguous tickets
- Graceful degradation: if LLM fails, rule-based result is used
- Decisions: `auto_resolve`, `agent_resolution`, `human_escalation`, `information_request`

### ResolutionAgent
- Generates a multi-step resolution plan via Claude
- Executes each step through the tool registry
- Compliance check gates every tool call
- Exceptions in `execute_tool` are caught per-step — one failure doesn't abort the run
- Tools: `reset_password`, `unlock_account`, `push_vpn_config`, `install_software`, `run_diagnostic`, `repair_application`, `reset_network_adapter`, `check_service_status`, `send_user_notification`, `update_ticket`

### ComplianceAgent
- Rule engine runs before every tool execution
- SEC-001: password reset requires `identity_verified=True`
- SEC-002: admin grants always blocked (requires human approval)
- POL-001: software installs require `software_id`
- Approval-required actions: `delete_user_account`, `grant_admin_access`, `modify_security_group`, `export_user_data`, `disable_mfa`, `access_privileged_system`

### Rate Limiter
- Sliding window: 60 RPM / 50k TPM (compliance), 50 RPM / 100k TPM (triage), 40 RPM / 80k TPM (resolution)
- Async lock released before `asyncio.sleep` — no deadlock under concurrent requests

---

## Testing

```powershell
# All 213 tests
venv\Scripts\python.exe -m pytest tests/ -v

# Edge cases only (164 tests)
venv\Scripts\python.exe -m pytest tests/test_edge_cases.py -v

# Original unit tests (49 tests)
venv\Scripts\python.exe -m pytest tests/test_agents.py -v

# With coverage
venv\Scripts\python.exe -m pytest tests/ -v --cov=src --cov-report=term-missing
```

Test coverage areas:
- Agent classification (empty input, unicode, very long, conflicting keywords)
- LLM fallback paths (invalid output, exceptions, all decision types)
- Resolution step execution (mixed success, tool exceptions, compliance blocking)
- Compliance rules (all approval-required actions, sensitive data patterns)
- Rate limiter (exact RPM limits, lock-not-held invariant, token tracking)
- API boundaries (min/max field lengths, enum validation, email format)
- XSS + SQL injection sanitization
- Chat flow logic (conversation history, ticket creation gating)
- Remediation engine (no plaintext passwords, approved/unapproved software)

---

## Local Cache

All model downloads and vector DB files stay inside the project:

```
.cache/
├── sentence-transformers/     # ~90MB — MiniLM embedding model
└── ...                        # HuggingFace model cache
.chroma/                       # ChromaDB collections
```

Set in `.env`:
```env
HF_HOME=./.cache
SENTENCE_TRANSFORMERS_HOME=./.cache/sentence-transformers
```

---

## Configuration

Key `.env` variables:

```env
ANTHROPIC_API_KEY=           # Required
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=50
RATE_LIMIT_TOKENS_PER_MINUTE=100000

# Optional integrations
SERVICENOW_INSTANCE=
SLACK_BOT_TOKEN=
AZURE_TENANT_ID=
```

---

## Monitoring

Prometheus metrics at `/metrics` (requires `pip install prometheus-client`):

- `agent_requests_total{agent, status}`
- `agent_request_duration_seconds{agent}`
- `tools_executed_total{tool, success}`
- `active_workflows`

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Make changes and run tests: `pytest tests/ -v`
4. Push and open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgments

- [Anthropic](https://anthropic.com) — Claude Sonnet 4.6
- [LangGraph](https://github.com/langchain-ai/langgraph) — Agent orchestration
- [FastAPI](https://fastapi.tiangolo.com) — Backend framework
- [ChromaDB](https://www.trychroma.com) — Vector database
- [React](https://reactjs.org) + [Vite](https://vitejs.dev) — Frontend

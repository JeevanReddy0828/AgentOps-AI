# 🤖 AgentOps AI - Intelligent IT Operations Platform

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4-orange.svg)](https://www.anthropic.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent IT Operations platform powered by multi-agent orchestration using Claude AI and LangGraph. The system automatically triages, resolves, and manages IT support tickets through specialized AI agents.

---

## 🌟 Features

- **Multi-Agent Architecture**: Specialized AI agents for triage, resolution, and compliance
- **Intelligent Chat Assistant**: Natural language IT support powered by Claude with automatic ticket creation
- **Automatic Ticket Creation**: Create tickets through conversation - just say "create a ticket"
- **RAG-Enhanced Knowledge Base**: Context-aware responses using ChromaDB
- **Real-time Dashboard**: Monitor tickets, agent performance, and analytics
- **Automated Remediation**: Execute common fixes (password resets, VPN configs, account unlocks)
- **Ticket Management**: View, track, and manage support tickets with detailed status

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│         (Dashboard | Tickets | AI Chat Assistant)               │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API
┌─────────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend                            │
│                    (src/api/main.py)                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                  LangGraph Orchestrator                         │
│              (Multi-Agent State Machine)                        │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│   Triage    │  Resolution │  Compliance │    Escalation         │
│   Agent     │    Agent    │    Agent    │      Agent            │
└─────────────┴─────────────┴─────────────┴───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    Knowledge Base (RAG)                         │
│                       ChromaDB                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API Key ([Get one here](https://console.anthropic.com/))

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/agentic-it-ops.git
cd agentic-it-ops
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install project in development mode
pip install -e .
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Environment Variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your-api-key-here
```

Or set it directly:

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "your-api-key-here"
```

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### 5. Run the Application

**Terminal 1 - Backend:**
```bash
uvicorn src.api.main:app --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### 6. Access the Application

| Service | URL |
|---------|-----|
| 🖥️ Frontend Dashboard | http://localhost:5173 |
| 📚 API Documentation | http://localhost:8000/docs |
| ❤️ Health Check | http://localhost:8000/health |

---

## 📁 Project Structure

```
agentic-it-ops/
├── src/
│   ├── agents/                 # AI Agent implementations
│   │   ├── base_agent.py       # Abstract base with Claude integration
│   │   ├── triage_agent.py     # Ticket classification & routing
│   │   ├── resolution_agent.py # Autonomous problem solving
│   │   ├── compliance_agent.py # Security & policy validation
│   │   └── escalation_agent.py # Human handoff management
│   │
│   ├── workflows/              # LangGraph workflow definitions
│   │   └── orchestrator.py     # Multi-agent state machine
│   │
│   ├── tools/                  # Agent tools & integrations
│   │   └── remediation.py      # AD, VPN, software deployment tools
│   │
│   ├── rag/                    # RAG pipeline components
│   │   ├── knowledge_base.py   # ChromaDB indexing & management
│   │   └── retriever.py        # Context retrieval with reranking
│   │
│   ├── api/                    # FastAPI application
│   │   └── main.py             # Application entry point
│   │
│   ├── models/                 # Pydantic data models
│   │   ├── ticket.py           # Ticket schemas
│   │   └── agent_state.py      # Agent state models
│   │
│   └── utils/                  # Utilities
│       ├── rate_limiter.py     # Token bucket rate limiter
│       ├── security.py         # Security helpers
│       └── observability.py    # Tracing & metrics
│
├── frontend/                   # React dashboard
│   ├── src/
│   │   └── App.jsx             # Main application component
│   └── package.json
│
├── tests/                      # Test suite
├── config/                     # Configuration files
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🎯 Usage

### 💬 AI Chat Assistant

The AI Chat Assistant provides natural language IT support with automatic ticket creation.

**How to Use:**

1. Navigate to the **AI Assistant** tab
2. Describe your IT issue in natural language
3. The assistant will troubleshoot or offer to create a ticket
4. Say **"create a ticket"** to generate a support ticket automatically

**Features:**
- Conversational troubleshooting with context awareness
- Smart categorization (auto-detects issue type and priority)
- Quick action buttons for common requests
- Seamless ticket creation from chat

**Example Conversation:**

```
User: VPN won't connect, tried restarting and different servers, need help ASAP
Assistant: I can see you have tried the standard troubleshooting steps.
          Let me create a support ticket for our IT team.
          Just say "create a ticket" to confirm.

User: create a ticket

Assistant: I have created ticket **INC8A2B3C4D** for you!
           - Issue: Network/VPN Connectivity Issue
           - Category: Network
           - Priority: High
           Our IT team will review it shortly.
```

### 🎫 Manual Ticket Creation

1. Go to the **Tickets** tab
2. Click **New Ticket**
3. Fill in title, description, category, and priority
4. Click **Create Ticket**

### 📊 Dashboard

View real-time metrics:
- Total tickets and resolution rates
- Auto-resolved vs escalated tickets
- Average resolution time
- Agent performance metrics
- Tickets by category breakdown

### 🔍 Ticket Details

Click on any ticket to view:
- Full ticket information
- Resolution status and progress
- Actions taken by AI agents
- Escalation details (if applicable)

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Chat with AI assistant |
| `/api/v1/tickets` | POST | Create a new ticket |
| `/api/v1/tickets/{id}` | GET | Get ticket details |
| `/api/v1/tickets/{id}/status` | GET | Get resolution status |
| `/api/v1/analytics/dashboard` | GET | Get dashboard metrics |
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |

---

## 🤖 Agent Capabilities

### Triage Agent
- Classifies tickets by category (network, hardware, software, access, email)
- Assigns priority based on urgency keywords
- Routes to appropriate resolution path

### Resolution Agent
- Executes automated remediation actions
- Password resets and account unlocks
- VPN configuration pushes
- Software installation/repair
- Network adapter resets

### Compliance Agent
- Validates actions against security policies
- Ensures audit trail compliance
- Checks for sensitive data handling

### Escalation Agent
- Handles complex issues requiring human intervention
- Manages handoff to IT staff
- Tracks escalation reasons

---

## 🛠️ Configuration

### Rate Limiting

Agents have built-in rate limiting to prevent API abuse:

```python
# Default limits
Triage Agent: 50 RPM, 100k TPM
Resolution Agent: 40 RPM, 80k TPM
Compliance Agent: 60 RPM, 50k TPM
```

### Knowledge Base

Add documents to the knowledge base for RAG:

```python
from src.rag.knowledge_base import KnowledgeBase

kb = KnowledgeBase()
kb.add_document(
    content=\"VPN troubleshooting steps...\",
    metadata={\"source\": \"IT Runbook\", \"category\": \"network\"}
)
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_agents.py
```

---

## 🐳 Docker (Optional)

```bash
# Build and run with Docker Compose
docker-compose up --build
```

---

## 📊 Monitoring

The application exposes Prometheus metrics at `/metrics`:

- `tickets_created_total`
- `tickets_resolved_total`
- `agent_request_duration_seconds`
- `agent_errors_total`

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m \"Add amazing feature\"`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) - Claude API
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [FastAPI](https://fastapi.tiangolo.com) - Backend framework
- [ChromaDB](https://www.trychroma.com) - Vector database
- [React](https://reactjs.org) - Frontend framework

---
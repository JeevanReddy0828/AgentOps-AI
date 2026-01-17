# 🤖 AgentOps AI - Intelligent IT Operations Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade **Agentic AI platform** for autonomous IT operations, featuring multi-agent orchestration, RAG-powered knowledge retrieval, and self-healing automation workflows. Built to transform end-user support through intelligent ticket resolution and proactive incident management.

![Architecture](docs/architecture.png)

## 🎯 Overview

AgentOps AI leverages cutting-edge agentic frameworks to autonomously resolve IT support tickets, implement self-healing remediation, and provide intelligent self-service capabilities. The platform reduces mean time to resolution (MTTR) by up to 70% while maintaining enterprise security and compliance standards.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Autonomous Ticket Resolution** | AI agents that analyze, categorize, and resolve common IT tickets without human intervention |
| **Multi-Agent Orchestration** | Coordinated agent workflows using LangGraph for complex incident handling |
| **RAG-Powered Knowledge Base** | Vector-indexed IT documentation for context-aware troubleshooting |
| **Self-Healing Automation** | Proactive detection and auto-remediation of system issues |
| **Security-First Design** | Zero-trust principles embedded in every workflow |
| **Real-time Analytics** | Comprehensive dashboards for monitoring automation effectiveness |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AgentOps AI Platform                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Chatbot    │  │  Self-Service│  │   Slack/     │  │   ServiceNow │     │
│  │   Portal     │  │    Portal    │  │   Teams Bot  │  │   Integration│     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │             │
│         └─────────────────┴────────┬────────┴─────────────────┘             │
│                                    │                                        │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐  │
│  │                        FastAPI Gateway                                │  │
│  │              (Authentication, Rate Limiting, Routing)                 │  │
│  └─────────────────────────────────┬─────────────────────────────────────┘  │
│                                    │                                        │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐  │
│  │                    Agent Orchestrator (LangGraph)                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │  Triage     │  │ Resolution  │  │ Escalation  │  │ Compliance  │   │  │
│  │  │  Agent      │  │ Agent       │  │ Agent       │  │ Agent       │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │  │
│  │         │                │                │                │          │  │
│  │         └────────────────┴────────┬───────┴────────────────┘          │  │
│  └───────────────────────────────────┼───────────────────────────────────┘  │
│                                      │                                      │
│  ┌───────────────┬───────────────────┼───────────────────┬───────────────┐  │
│  │               │                   │                   │               │  │
│  │  ┌────────────▼────────────┐  ┌───▼───────────┐  ┌────▼────────────┐  │  │
│  │  │   RAG Knowledge Base    │  │  Tool Registry│  │  Action Engine  │  │  │
│  │  │   (ChromaDB + OpenAI)   │  │               │  │                 │  │  │
│  │  │   • IT Runbooks         │  │  • JIRA       │  │  • Script Exec  │  │  │
│  │  │   • Troubleshooting     │  │  • ServiceNow │  │  • API Calls    │  │  │
│  │  │   • Compliance Docs     │  │  • AD/Entra   │  │  • Remediation  │  │  │
│  │  │   • Historical Tickets  │  │  • Slack      │  │  • Notifications│  │  │
│  │  └─────────────────────────┘  └───────────────┘  └─────────────────┘  │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Observability & Security Layer                   │   │
│  │  • OpenTelemetry Tracing  • Prometheus Metrics  • Audit Logging      │   │
│  │  • Security Event Monitoring  • Compliance Validation                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key (or Azure OpenAI endpoint)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agentops-ai.git
cd agentops-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and configurations

# Start infrastructure (Redis, ChromaDB)
docker-compose up -d

# Initialize the knowledge base
python -m src.rag.indexer --init

# Run the application
uvicorn src.api.main:app --reload --port 8000
```

### Running with Docker

```bash
docker-compose -f docker-compose.full.yml up --build
```

## 📁 Project Structure

```
agentops-ai/
├── src/
│   ├── agents/                    # AI Agent definitions
│   │   ├── __init__.py
│   │   ├── base_agent.py          # Abstract base agent class
│   │   ├── triage_agent.py        # Ticket classification & routing
│   │   ├── resolution_agent.py    # Autonomous problem solving
│   │   ├── escalation_agent.py    # Human handoff management
│   │   └── compliance_agent.py    # Security & policy validation
│   │
│   ├── workflows/                 # LangGraph workflow definitions
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Main agent orchestration graph
│   │   ├── ticket_workflow.py     # Ticket resolution workflow
│   │   └── incident_workflow.py   # Incident management workflow
│   │
│   ├── tools/                     # Agent tools & integrations
│   │   ├── __init__.py
│   │   ├── servicenow.py          # ServiceNow API integration
│   │   ├── active_directory.py    # AD/Entra ID operations
│   │   ├── slack_notifier.py      # Slack notifications
│   │   └── remediation.py         # Auto-remediation scripts
│   │
│   ├── rag/                       # RAG pipeline components
│   │   ├── __init__.py
│   │   ├── indexer.py             # Document indexing
│   │   ├── retriever.py           # Context retrieval
│   │   └── knowledge_base.py      # KB management
│   │
│   ├── api/                       # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                # Application entry point
│   │   ├── routes/                # API route handlers
│   │   └── middleware/            # Auth, logging, security
│   │
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   ├── ticket.py              # Ticket schemas
│   │   └── agent_state.py         # Agent state models
│   │
│   └── utils/                     # Utilities
│       ├── __init__.py
│       ├── security.py            # Security helpers
│       └── observability.py       # Tracing & metrics
│
├── frontend/                      # React dashboard
├── tests/                         # Test suite
├── config/                        # Configuration files
├── docs/                          # Documentation
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🤖 Agent System

### Agent Types

#### 1. Triage Agent
Analyzes incoming tickets and determines optimal resolution path.

```python
from src.agents import TriageAgent

agent = TriageAgent()
result = agent.analyze(ticket={
    "title": "Cannot access VPN",
    "description": "Getting timeout errors when connecting to corporate VPN",
    "user_email": "john.doe@company.com"
})
# Returns: category, priority, suggested_resolution_path
```

#### 2. Resolution Agent
Executes autonomous troubleshooting and remediation.

```python
from src.agents import ResolutionAgent

agent = ResolutionAgent()
result = await agent.resolve(
    ticket_id="INC001234",
    context=retrieved_knowledge,
    available_tools=["password_reset", "vpn_config", "ad_unlock"]
)
```

#### 3. Escalation Agent
Manages handoffs to human operators when needed.

#### 4. Compliance Agent
Validates all actions against security policies before execution.

### Multi-Agent Workflow

```python
from src.workflows import TicketResolutionWorkflow

workflow = TicketResolutionWorkflow()
result = await workflow.execute(
    ticket_id="INC001234",
    max_iterations=5,
    require_compliance_check=True
)
```

## 🔍 RAG Pipeline

The RAG system indexes IT documentation, historical tickets, and runbooks for context-aware troubleshooting.

### Indexing Documents

```python
from src.rag import KnowledgeBase

kb = KnowledgeBase()

# Index IT documentation
kb.index_documents(
    source="./docs/runbooks/",
    doc_type="runbook",
    metadata={"department": "IT", "category": "network"}
)

# Index historical tickets for pattern learning
kb.index_tickets(
    tickets=resolved_tickets,
    extract_solutions=True
)
```

### Retrieval with Reranking

```python
from src.rag import ContextRetriever

retriever = ContextRetriever(
    top_k=10,
    rerank=True,
    min_relevance_score=0.7
)

context = retriever.retrieve(
    query="VPN connection timeout corporate network",
    filters={"category": "network", "doc_type": "runbook"}
)
```

## 🔧 Available Tools

| Tool | Description | Auto-Execute |
|------|-------------|--------------|
| `password_reset` | Reset user passwords in AD/Entra | ✅ |
| `account_unlock` | Unlock locked user accounts | ✅ |
| `vpn_config_push` | Push VPN configuration to user device | ✅ |
| `software_install` | Trigger software deployment via SCCM | ⚠️ Approval |
| `ticket_update` | Update ServiceNow ticket status | ✅ |
| `slack_notify` | Send notifications to users/channels | ✅ |
| `run_diagnostic` | Execute diagnostic scripts remotely | ⚠️ Approval |

## 📊 API Endpoints

### Tickets

```
POST   /api/v1/tickets              # Create new ticket
GET    /api/v1/tickets/{id}         # Get ticket details
POST   /api/v1/tickets/{id}/resolve # Trigger autonomous resolution
GET    /api/v1/tickets/{id}/status  # Get resolution status
```

### Chat Interface

```
POST   /api/v1/chat                 # Send message to AI assistant
GET    /api/v1/chat/history/{id}    # Get conversation history
POST   /api/v1/chat/feedback        # Submit feedback on response
```

### Analytics

```
GET    /api/v1/analytics/dashboard  # Get dashboard metrics
GET    /api/v1/analytics/trends     # Resolution trends over time
GET    /api/v1/analytics/agents     # Agent performance metrics
```

## 🔐 Security Features

- **Zero-Trust Architecture**: Every action validated against security policies
- **Role-Based Access Control**: Granular permissions for agent capabilities
- **Audit Logging**: Complete audit trail for all automated actions
- **Secret Management**: Integration with HashiCorp Vault for credentials
- **Compliance Validation**: Pre-execution checks against IT policies

## 📈 Metrics & Observability

### Key Metrics Tracked

- **MTTR** (Mean Time to Resolution)
- **Automation Rate** (% of tickets resolved autonomously)
- **First Contact Resolution Rate**
- **Agent Confidence Scores**
- **Escalation Rates**

### Observability Stack

- **Tracing**: OpenTelemetry with Jaeger
- **Metrics**: Prometheus + Grafana
- **Logging**: Structured logging with correlation IDs

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

## 🚢 Deployment

### Kubernetes (Helm)

```bash
helm repo add agentops https://charts.agentops.ai
helm install agentops agentops/agentops-ai \
  --set openai.apiKey=$OPENAI_API_KEY \
  --set servicenow.instance=$SNOW_INSTANCE
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `CHROMA_HOST` | ChromaDB host | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `SERVICENOW_INSTANCE` | ServiceNow instance URL | No |
| `SLACK_BOT_TOKEN` | Slack bot token | No |

## 📚 Documentation

- [Architecture Deep Dive](docs/architecture.md)
- [Agent Development Guide](docs/agent-development.md)
- [RAG Configuration](docs/rag-configuration.md)
- [Security Best Practices](docs/security.md)
- [API Reference](docs/api-reference.md)

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://langchain.com/) & [LangGraph](https://langchain-ai.github.io/langgraph/) for agent orchestration
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [FastAPI](https://fastapi.tiangolo.com/) for the API framework

---

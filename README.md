# Agentic RAG Platform

End-to-end, containerized Agent Swarm + RAG platform. Upload PDFs, parse -> chunk -> embed, store in Milvus, and query via FastAPI. Conversations are threaded and persisted in MongoDB (Beanie). Includes hybrid retrieval (dense + BM25), idempotent Milvus bootstrap, seeded customer data, and a Customer Support Agent with typed tools.

> Important: You must provide a valid OpenAI API key via environment variable.

---

## ✨ Highlights

- Threaded conversations persisted in MongoDB (Beanie), no SQLite.
- Multi-agent "Swarm" with Router, Knowledge, and Customer Support agents (handoffs included).
- RAG pipeline with:
  - PDF parsing (PyMuPDF), chunking with overlap.
  - Embeddings (OpenAI), stored in Milvus.
  - Hybrid retrieval (dense + BM25) using Milvus REST v2 advanced_search.
- Typed tools for Customer Support:
  - customer_support.get_support_overview
  - customer_support.create_ticket
- Beanie ODM with UTC timestamps and robust logging (loguru).
- Idempotent Milvus bootstrap on startup (collection, indexes, load).
- Docker Compose for one-command bring-up.
- Swagger/OpenAPI docs exposed by FastAPI.

---

## 🧠 Agent Swarm Architecture

- Router Agent (entry point)
  - Classifies each user message and dispatches to specialized agents.
  - Can "handoff" between agents as needed (e.g., from router -> knowledge or customer_support).
- Knowledge Agent
  - Answers questions about InfinitePay products/services using RAG.
  - Uses hybrid retrieval (Milvus) and optionally Web Search for general queries.
  - Data sources suggested by the challenge (website pages) can be exported to PDF or crawled and then ingested.
- Customer Support Agent
  - Retrieves user account context, explains issues (KYC, transfers, login), and creates support tickets.
  - Tools:
    - customer_support.get_support_overview(user_id)
    - customer_support.create_ticket(user_id, subject, description)

Message flow

- POST /agents/run -> Router Agent -> may handoff to Knowledge or Customer Support.
- History is loaded from Mongo by thread_id and passed to the model; responses are appended back to the same thread.

---

## 🧰 Tech Stack

- Language: Python 3.13
- API: FastAPI
- DB (metadata): MongoDB + Beanie (Pydantic v2)
- Vector DB: Milvus REST v2 (HNSW + Sparse BM25)
- Parsing: PyMuPDF (PDF)
- Embeddings: OpenAI
- Logging: loguru
- Metrics: Prometheus (via prometheus-client)
- Containers: Docker + Docker Compose

---

## 🗂️ Project Structure (high level)

```
app/
  agents/           # controllers, models (DAO), routes, schemas
  core/
    agents/         # engine, loader, tools, config schema
      tools/        # customer_support tools, etc.
    connectors/     # milvus bootstrap + REST clients
    pdf_uploader/   # parse, chunk, embed, ingest
    db/             # TimestampingMixin
    metrics.py
    utils.py
  customers/        # DAOs, schemas, seed
  rag/              # DAOs, controllers, routes, schemas
  settings.py
resources/
  agents.yaml       # model defaults, tools, agents (with handoffs)
  prompts/
    router_agent.md
    knowledge_agent.md
    customer_support_agent.md
docker-compose.yaml
Dockerfile
```

---

## ⚙️ Environment

Create environments/.env (Compose uses this file)

Copy the provided template and add your OpenAI key:

```
cp environments/test.env environments/.env
# edit environments/.env and set OPENAI_API_KEY
```

Example environments/.env (fill in your OPENAI_API_KEY):

```
# OpenAI
OPENAI_API_KEY=...

# Mongo
MONGO_URI=mongodb://mongo:27017
MONGO_DB=ragdb

# Milvus REST
MILVUS_URL=http://milvus-standalone:9091
MILVUS_SECRET=
MILVUS_COLLECTION=doc_chunks

# Agents
AGENTS_CONFIG_PATH=resources/agents.yaml
```

---

## ▶️ How to Run

Option A — Docker Compose (recommended)

```
docker compose -f ./docker-compose.yaml --env-file environments/.env up --build api

```

Option B — VS Code "one-click"

- The repo includes a dev/watch setup for the api-debug service.
- Use the provided .vscode setup to run the "API (debug)" target without typing the full compose command:
  - Equivalent to:
    ```
    docker compose -f ./docker-compose.yaml --env-file environments/.env up --build --remove-orphans api-debug --watch
    ```
- Hot-reload syncs the /app directory into the running container (via compose "develop.watch").

Swagger

- After the API is up, open the interactive docs:
  - http://localhost:8000/docs (Swagger)
  - http://localhost:8000/redoc (ReDoc)

---

## 🔌 API Endpoints

- Agents

  - POST /agents/run -> run a message through the agent swarm; returns the full thread (ThreadOut).
  - GET /agents/threads/{thread_id} -> retrieve an entire threaded conversation.

- RAG

  - POST /rag/upload -> upload one or more PDF files (multipart/form-data: files[]).
  - GET /rag/hybrid_search -> query Milvus by hybrid retrieval (dense + BM25).

- Metrics
  - GET /metrics -> Prometheus exposition.

> Threads: If thread_id is omitted in /agents/run, a new thread is created and reused subsequently. All messages are persisted in MongoDB and appended to the same thread.

---

## 🧵 Threads and Messages

- Every conversation is a thread persisted in MongoDB with timestamped messages (Beanie DAOs).
- /agents/run:
  - Creates a new thread if none is provided.
  - Saves the user's message, loads the full history, passes it to the model, saves assistant messages, and returns the full thread.
- /agents/threads/{id}:
  - Returns the thread with all messages (typed schema).

Example: start a new thread

```
curl -s -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Why am I not able to make transfers?", "user_id":"client123"}' | jq
```

Then continue the same thread (use the returned thread_id):

```
curl -s -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Please open a ticket to expedite this.", "user_id":"client123", "thread_id":"<thread_id>"}' | jq
```

Read the thread:

```
curl -s http://localhost:8000/agents/threads/<thread_id> | jq
```

---

## 🧭 Agents: Capabilities, Tools, and Example Prompts

### 1) Router Agent

- Role: entry point. Classifies intent and orchestrates handoffs:
  - Customer account issues -> Customer Support Agent.
  - Product/website questions -> Knowledge Agent.
  - General world questions/news -> Knowledge Agent + Web Search tool (or handoff to a web-search-capable agent if configured).

Example messages

- "What are the fees of the Maquininha Smart?"
- "Why I am not able to make transfers?"
- "Quais as principais notícias de São Paulo hoje?"

Outcome: routes to the appropriate agent/tool chain and returns a concise answer.

### 2) Knowledge Agent

- RAG-based. Fetches relevant chunks from Milvus and composes grounded responses.
- Can optionally use a hosted WebSearchTool for general news/current events.

Example messages (from the challenge)

- "What is the cost of the Maquininha Smart?"
- "What are the rates for debit and credit card transactions?"
- "How can I use my phone as a card machine?"

Data sources

- Suggested InfinitePay pages (challenge). Export them to PDF or ingest scraped HTML -> converted text -> chunks.
- The ingestion pipeline is generic; any text/PDF can be onboarded.

### 3) Customer Support Agent

- Uses internal tools to read and act on user context.
- Default language: pt-BR; responds in English if the user writes in English.
- Empathic, concise, privacy-aware.

Tools (typed)

- customer_support.get_support_overview(user_id: str) -> SupportOverview
  - Returns: Customer, Account (balance/holds), Compliance/KYC (transfer enabled/reason), Security (login/2FA/attempts), open/pending Tickets.
- customer_support.create_ticket(user_id: str, subject: str, description: str) -> TicketOut
  - Creates a ticket and returns typed data, including ticket_id.

Seeded sample users

- client789: KYC verified, transfers enabled, plan "pro", 2FA enabled.
- client123: KYC pending, transfers disabled ("KYC documents pending review"), login disabled, open ticket "TCK-1234ABCD".

Example questions

- "Why I am not able to make transfers?" -> Explains KYC pending; offers to open a ticket.
- "I can't sign in to my account." -> Detects login disabled/many failed attempts; advises steps; offers ticket creation.
- "Qual é meu saldo disponível?" -> Returns balance, holds, and available balance in BRL.
- "Tenho tickets abertos?" -> Lists open/pending tickets with id + subject.

---

## 📚 RAG Pipeline (How it works)

1. Upload

- POST /rag/upload with PDF files.

2. Parse

- PyMuPDF reads pages -> text is extracted. You can extend with OCR fallback if needed.

3. Chunk

- Fixed-size chunks (≈1200 chars) with overlap (≈150) to preserve context.

4. Embed

- OpenAI embeddings (dim=1536).

5. Store (Milvus)

- Insert embeddings into Milvus.
- The collection includes:
  - text (VarChar with analyzer enabled),
  - vector (FloatVector 1536),
  - sparse_vector (SparseFloatVector) automatically generated from text via BM25 function.

6. Search (Hybrid)

- GET /rag/hybrid_search uses Milvus advanced_search:
  - Two searches: dense vector and BM25 sparse vector.
  - Weighted re-rank with tunable weights.

Why Milvus?

- Familiarity and expertise with Milvus.
- Built-in support for dense vectors and sparse BM25 functions.
- "Advanced search" API enables a single weighted hybrid call.
- Excellent performance and simple REST deployment.

Example upload

```
curl -s -X POST http://localhost:8000/rag/upload \
  -F "files=@./docs/infinitepay-overview.pdf" \
  -F "files=@./docs/maquininha.pdf" | jq
```

Example hybrid search

```
curl -s "http://localhost:8000/rag/hybrid_search?query=What%20are%20the%20fees%20of%20the%20Maquininha%20Smart&top_k=5&dense_weight=0.5&sparse_weight=0.5" | jq
```

---

## 🗃️ Data Model (MongoDB + Milvus)

MongoDB (Beanie DAOs)

- Agents
  - ThreadDAO: "threads_v2"
  - MessageDAO: "messages_v2"
  - RunLogDAO: "agent_runs"
- Customers
  - CustomerDAO: "customers"
  - AccountDAO: "accounts"
  - ComplianceDAO: "compliance"
  - SecurityDAO: "security"
  - TicketDAO: "tickets"
- RAG
  - FileDAO: "files"
  - ChunkDAO: "chunks"

Milvus

- Collection: doc_chunks
  - Fields: chunk_id, file_id, filename, title, page_idx, chunk_idx, source, text, sparse_vector (BM25), vector (FloatVector 1536)
  - Indexes: HNSW on vector (COSINE), SPARSE_INVERTED_INDEX on sparse_vector (BM25)

---

## 🧾 Agents YAML (Adding agents and tools)

Location: resources/agents.yaml

Key sections:

- model_defaults: provider/model/temperature/max_turns.
- tools: each tool is either "hosted" (e.g., WebSearchTool) or "python_function" (your module function).
- agents: define name, prompt_file, tool_refs, handoffs.
- entry_agent: the agent that receives the first message (router).

Example snippet

```yaml
model_defaults:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.2
  max_turns: 8

entry_agent: router_agent

tools:
  - name: customer_support.get_support_overview
    kind: python_function
    dotted_path: app.core.agents.tools.customer_overview:get_support_overview

  - name: customer_support.create_ticket
    kind: python_function
    dotted_path: app.core.agents.tools.create_ticket:create_ticket

  - name: web.search
    kind: hosted
    type: WebSearchTool

agents:
  - name: router_agent
    prompt_file: resources/prompts/router_agent.md
    tool_refs: [web.search] # optional tools the router can call
    handoffs: [knowledge_agent, customer_support_agent]

  - name: knowledge_agent
    prompt_file: resources/prompts/knowledge_agent.md
    tool_refs: [] # attach RAG tools here if desired
    handoffs: []

  - name: customer_support_agent
    prompt_file: resources/prompts/customer_support_agent.md
    tool_refs:
      - customer_support.get_support_overview
      - customer_support.create_ticket
    handoffs: []
```

Adding a new tool (python_function)

- Implement a function and an Arguments class (Pydantic v2) in a module.
- The function signature must be async def func(ctx: RunContextWrapper[Any], args: Arguments) -> BaseModel (or dict).
- Add it under tools with kind: python_function and dotted_path: "module:function".
- The loader auto-extracts the JSON schema from Arguments and wraps return values (BaseModel -> dict).
  - If the Arguments fields are typed with descriptions, they appear for the agent to understand the usage.
  - For example, the Field(..., description="<description>") is used in the prompt.

Example tool module

```python
from pydantic import BaseModel
from agents import RunContextWrapper

class Arguments(BaseModel):
  value: int = Field(..., description="An integer value to increment")

async def my_action(ctx: RunContextWrapper[Any], args: Arguments) -> dict:
  """
  Increments ‘value' by 1
  """
  parsed = Arguments.model_validate_json(args)
  value = parsed.value
  return {"new_value": value + 1}
```

Adding a new agent

- Create a prompt file under resources/prompts.
- Define the agent in YAML with the prompt_file.
- Reference any tools it needs in tool_refs.
- (Optional) Add handoffs for routing paths.

---

## 📑 Example Requests (curl)

Agents: new thread

> Important! This query will make the knowledge agent call RAG. Make sure you have uploaded and indexed the PDFs to get results from RAG.

```
curl -s -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{"message":"What are the fees of the Maquininha Smart?", "user_id":"client789"}' | jq
```

Agents: continue thread

```
curl -s -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Could you also explain debit vs credit rates?", "user_id":"client789", "thread_id":"<thread_id>"}' | jq
```

Agents: customer support, transfer issue

```
curl -s -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Why I am not able to make transfers?", "user_id":"client123"}' | jq
```

RAG: upload PDFs

```
curl -s -X POST http://localhost:8000/rag/upload \
  -F "files=@./docs/infinitepay-overview.pdf" \
  -F "files=@./docs/maquininha.pdf" | jq
```

RAG: hybrid search

```
curl -s "http://localhost:8000/rag/hybrid_search?query=What%20are%20the%20rates%20for%20debit%20and%20credit%20card%20transactions%3F&top_k=5&dense_weight=0.5&sparse_weight=0.5" | jq
```

Swagger/OpenAPI

```
open http://localhost:8000/docs
```

---

## 🧪 Testing (strategy and examples)

Note: Due to time constraints, full test coverage was not implemented. Below is the strategy and minimal examples showing how I would proceed using pytest with mocks.

What I would unit/integration test

- Agents
  - POST /agents/run: new thread creation, appending to existing threads, persistence of assistant messages.
  - GET /agents/threads/{id}: ordering, schema integrity.
  - Router decisions: message classification -> correct handoffs (mock Runner).
- Tools
  - customer_support.get_support_overview: presence/absence of each domain (customer/account/compliance/security/tickets).
  - customer_support.create_ticket: happy path and validation.
- RAG
  - POST /rag/upload: duplicate detection (file_hash), file/chunk persistence, failure rollback (delete_file_and_chunks).
  - GET /rag/hybrid_search: shape normalization and ranking order.
- Connectors
  - Milvus insert/search: error handling, timeouts; ensure payloads comply with advanced_search.
- Infra
  - Milvus bootstrap idempotency.
  - Beanie init and indexes.

Example: test /agents/run with mocks

```python
# tests/test_agents_run.py
import pytest
from httpx import AsyncClient
from fastapi import FastAPI

@pytest.mark.asyncio
async def test_agents_run_new_thread(monkeypatch, app: FastAPI):
    # Mock engine.run to return a minimal object with raw_responses
    class DummyResult:
        last_agent = type("A", (), {"name": "router_agent"})()
        raw_responses = [type("R", (), {"output": [["unused"], [{"text": "Hello!"}]]})()]

    from app.core.agents import engine as eng
    async def fake_run(*args, **kwargs):
        return DummyResult()
    monkeypatch.setattr(eng.get_engine(), "run", fake_run)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/agents/run", json={"message": "Hi", "user_id": "u-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "thread_id" in data
        assert len(data["messages"]) >= 1
```

Example: test RAG upload with mocked embedder + Milvus

```python
# tests/test_rag_upload.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_rag_upload(monkeypatch, app):
    # Mock embedder.encode to return dummy vectors
    from app.core.pdf_uploader.embedder import AsyncEmbedder
    async def fake_encode(texts):
        return [[0.0] * 1536 for _ in texts]
    monkeypatch.setattr(AsyncEmbedder, "encode", fake_encode)

    # Mock MilvusInsert.insert to accept inserts
    from app.core.connectors.milvus import MilvusInsert
    async def fake_insert(self, data):
        return {"code": 0}
    monkeypatch.setattr(MilvusInsert, "insert", fake_insert)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        files = {"files": ("doc.pdf", b"%PDF-1.5 fake pdf ...", "application/pdf")}
        resp = await ac.post("/rag/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["documents_indexed"] >= 0
```

Also, I would also add fixtures for a temporary MongoDB database or use a test collection, and isolate Milvus calls with mocks.

---

## 🧩 Customer Support: Prompt and Tools

Prompt

- resources/prompts/customer_support_agent.md
  - Portuguese by default; switches to English if user uses English.
  - Calls overview tool by default for account-related queries.
  - Offers to create a ticket.

Tools

- customer_support.get_support_overview(user_id: str) -> SupportOverview
  - Returns a unified, typed snapshot: customer/account/compliance/security/tickets.
- customer_support.create_ticket(user_id: str, subject: str, description: str) -> TicketOut
  - Creates a ticket; returns typed payload (ticket_id, timestamps, etc.).

---

## 🧱 Design Choices

- Beanie ODM with Pydantic v2 for typed DAOs, UTC timestamps, and validation on assignment.
- Threads/messages persisted in Mongo instead of SQLite, enabling auditable, multi-session conversations.
- Milvus chosen for:
  - Familiarity and prior experience.
  - Strong hybrid capabilities (dense + sparse BM25) via advanced_search.
  - Good performance and simple REST deployment.
- YAML-driven agent/tool wiring:
  - Easier to add/replace tools and agents without code changes.
  - Pydantic "Arguments" class gives typed params + JSON schema for each tool automatically.

---

## 📈 Metrics & Observability

- GET /metrics: Prometheus exposition
  - Upload counters, duplicate counters, chunk counters.
  - Embed/insert/search latencies per stage.
- Structured logging: loguru across controllers, ingestion, and bootstrap.
- Error handling:
  - Duplicate detection (file_hash).
  - Batch errors in Milvus insert return detailed messages.
  - Cleanup path when all chunks fail to index.

---

## 🚧 Limitations & Next Steps

- Tests: Not implemented due to time; proposed pytest plan and mock patterns above.
- RAG sources: For the InfinitePay site, ingest the exported/crawled content as PDFs/markdown into the same pipeline (or add a small HTML ingestion utility).
- Expand Customer Support tools:
  - Unlock account, enable 2FA, prioritize KYC review (with proper guards).
- Add guardrails and escalation-to-human mechanism (bonus from the challenge).
- Add a 4th agent (e.g., a Slack or Incident agent) for internal workflows.

---

## ✅ Quick Start Checklist

- Set environments/.env with OPENAI*API_KEY, MONGO*\_, MILVUS\_\_.
- docker compose up --build
- Confirm:
  - Mongo and Milvus are healthy.
  - "Beanie initialized", "Seed customers done", "Milvus bootstrap completed" in logs.
- Upload PDFs with /rag/upload (optional).
- Ask a question via /agents/run; inspect the thread_id and GET /agents/threads/{id}.
- Explore via Swagger at /docs.

---

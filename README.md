# agentic-rag-platform

End-to-end, containerized RAG system to upload PDFs, parse + chunk + embed, store in Milvus, and answer questions via a clean FastAPI + Streamlit UI. Includes OCR fallback, hybrid (dense + sparse/BM25) retrieval, metrics, and structured logging.

> ATTENTION: OPENAI_API_KEY needed!

---

## 💡 Features

- **Upload PDFs** (multi-file) → parse with **PyMuPDF**; **OCR fallback** for pages with missing Unicode maps.
- **Chunking** with overlap → **OpenAI embeddings** (small model) → **Milvus** (dense vector + **auto sparse** via BM25).
- **Hybrid search** (dense + BM25) with weighted re-rank.
- **MongoDB** for file + chunk metadata (and dedupe via file hash).
- **FastAPI** backend, **Streamlit** UI.
- **Prometheus** metrics + a **Metrics** page (avg/p50/p90/p99 per stage + histograms).
- **Structured logs** with **loguru**.
- **Docker Compose** for one-command bring-up.

---

## 🧰 Tech Stack

- **Language:** Python  
- **API:** FastAPI  
- **UI:** Streamlit  
- **Vector DB:** Milvus (REST v2)  
- **DB:** MongoDB  
- **Metrics:** prometheus-client (+ `/metrics` and `/ui-metrics`)  
- **Parsing:** PyMuPDF; **OCR fallback:** Pillow + pytesseract  
- **LLM:** OpenAI (e.g. `gpt-4o`)  
- **Embedding:** OpenAI `text-embedding-3-small` (dim **1536**)  
- **Retrieval:** Zilliz/Milvus **hybrid** (dense + BM25)  
- **Logging:** loguru  
- **Container:** Docker / Docker Compose

---

## 🗂️ Project Structure (high level)
``` 
app/
    core/ # core logic (ingest, chunking, OCR fallback, embed, milvus, search)
    applications-folders...
    settings.py # env handling (incl. *_FILE secrets)
ui.py # Streamlit app (Chat + Metrics pages)
docker-compose.yml
Dockerfile
requirements.txt
``` 


---

## 🔌 API

**Routes**
- `POST /documents` — upload one or more PDFs (`multipart/form-data`, field `files`).  
  Returns: `{ message, documents_indexed, total_chunks, failed_chunks: [ ... ], failed_files: [ ... ] }`.
- `POST /question` — ask a question about the indexed docs.  
  Body: `{"question": "..."}` → `{ answer, sources/hits }`.
- `GET /health` — health check.
- `GET /metrics` — Prometheus exposition.
- `GET /ui-metrics` — compact JSON for the Streamlit Metrics page.

**Examples**

<!-- Upload:
```bash
curl -s -X POST http://localhost:8000/documents \
  -F "files=@LB5001.pdf" \
  -F "files=@MN414_0224.pdf" \
  -F "files=@WEG-CESTARI-manual-iom-guia-consulta-rapida-50111652-pt-en-es-web.pdf" \
  -F "files=@WEG-motores-eletricos-guia-de-especificacao-50032749-brochure-portuguese-web.pdf" \
  | jq
``` 

Ask:
```
curl -s -X POST http://localhost:8000/question \
  -H "Content-Type: application/json" \
  -d '{"question":"For which environments are ODP vs. TEFC motor enclosures intended?"}' \
  | jq
```  -->

---
## 🧱 Database Collections

### Milvus (collection: `doc_chunks`)
Created idempotently at startup with schema optimized for hybrid retrieval:

- `pk`: **Int64**, `autoID: true` (Milvus primary key)  
- `chunk_id`: VarChar(64) — deterministic logical ID (e.g., hash of `file_id:page:chunk`)
- `file_id`: VarChar(64)
- `filename`: VarChar(256)
- `title`: VarChar(256) — PDF `Title` or heuristically guessed
- `page_idx`: Int64
- `chunk_idx`: Int64
- `source`: VarChar(256) — e.g., `s3://...` or `file://...#page=7`
- `text`: VarChar(65535), **analyzer enabled** (e.g., portuguese/english)
- `sparse_vector`: **SparseFloatVector** — **auto-generated from `text`** via **BM25 function**
- `vector`: **FloatVector(1536)** — dense embedding

**Indexes**
- `vector`: HNSW (COSINE)  
- `sparse_vector`: SPARSE_INVERTED_INDEX (BM25)

> The BM25 function wires `text → sparse_vector`, so you **do not** send sparse vectors when inserting.

### MongoDB

**`file`**
```json
{
  "file_id": "str",
  "file_hash": "sha256",
  "filename": "str|null",
  "title": "str|null",
  "content": "str",
  "total_pages": 123,
  "size_bytes": 123456,
  "mime": "application/pdf",
  "created_at": "datetime"
}
``` 
**`chunk`**
```json
{
  "chunk_id": "str",
  "file_id": "str",
  "filename": "str",
  "title": "str|null",
  "page_idx": 0,
  "chunk_idx": 0,
  "source": "str",
  "text": "str"
}
```

## 🧠 RAG Decisions

- **Chunking:** ~**1200 chars** with **150 overlap**. Small enough to keep answers specific; large enough to preserve context across headings/sentences.  
- **Signals in metadata:** store `filename`, `page_idx`, `file_id`, `title` in each chunk to help the retriever bias results when the user targets a specific file.  
- **Hybrid weights:** start with balanced weights; a small LLM prompt decides final blend (dense vs. sparse) based on the query’s lexical/symbolic strength.  
- **Dedup:** **file hash (sha256)** prevents re-embedding identical files.

---

## 🧾 Questions and Responses Examples

### 1) For which environments are ODP vs. TEFC motor enclosures intended?
**Answer:**

**Motor Enclosures: ODP vs. TEFC**

**ODP (Open Drip Proof) Enclosures:**
- Intended for clean, dry locations with adequate supply of cooling air.
- Not suitable for environments with flammable or combustible materials due to their design, which allows for water splashes but not direct exposure to elements.
- Suitable primarily for indoor applications.  
*Source:* “LB5001.pdf”, p.1.

**TEFC (Totally Enclosed Fan Cooled) Enclosures:**
- Designed for harsh environments, including those with moisture, dust, and other contaminants.
- Provide robust protection against environmental factors, making them suitable for both indoor and outdoor applications.

---

### 2) At 1800 RPM, what is the relubrication interval for NEMA frames up to and including 210?
**Answer:**  
For NEMA frames up to and including 210, the recommended relubrication interval at 1800 RPM is **12,000 hours**. This information is detailed in the document provided, which lists relubrication intervals based on frame size and RPM. Therefore, for motors in this category, users should plan for maintenance accordingly, *<LB5001.pdf>, p.2.*

---

### 3) What maximum submergence/pressure limits apply at the external motor seal?
**Answer:**

**For Tandem Seal designs:**
- Maximum submergence is **160 ft (49 m)** depth.
- Maximum pressure is **100 PSI (690 kPa)**.

**For slurry seal designs:**
- The maximum external motor seal pressure is **15 PSI (103 kPa)**.

---

### 4) What does the moisture protection system include, and what happens if the outer seal fails?
**Answer:**

**The moisture protection system includes:**
- **Non-wicking cable cap assembly:** Prevents moisture from wicking through the cable assembly, even if the cable jacket is punctured.
- **Dual moisture sensing probes:** These probes extend into the oil chamber located between the tandem mechanical seals to detect moisture levels.

**If the outer seal fails:**
- Water can enter the oil chamber through labyrinth slinger paths, creating a water/oil emulsion.
- The presence of water increases conductivity in the moisture detector control, which applies voltage to the moisture probes and detects the moisture presence.
- Additionally, a leakage detector control system, such as the **Ametek APT Series 8040MD Moisture Detector**, must be connected for warranty and UL listing validity *(manual, p.10).*

---

### 5) What are the storage conditions (humidity and temperature)?
**Answer:**  
The recommended storage conditions for the gear units and gearmotors are as follows:

- **Relative Humidity:** Must be below **60%**.  
- **Ambient Temperature:** Should be between **-5°C and +40°C**.

These items should be stored in a closed environment that is dry, protected from vermin, and not directly exposed to sunlight or UV rays, free from dust, gases, fungi, and corrosive agents, such as contaminated air or solvents. If the relative humidity is below 50%, products can be stored for up to 3 years, while the general guidance allows for storage up to 2 years maximum under ideal conditions (not exceeding 60% humidity) *(WEG-CESTARI-manual-iom-guia-consulta-rapida-50111652-pt-en-es-web.pdf, p. 59).*

---

### 6) Within what time must gear units be put into operation after leaving the factory, and what to do if stored longer?
**Answer:**  
After leaving the factory, WEG-CESTARI gear units/gearmotors must be put into operation within a maximum period of **six months**. If they are out of operation for a period of six to nine months, it is recommended to fill the gear unit with proper lubricants, ensuring that the gears and rolling bearings are immersed in oil. Additionally, the high-speed shaft should be turned at least two complete revolutions and this should be repeated at least once every two months. **Before operation, any excess lubricant must be drained to the proper operational level (center of the sight glass)** *(<WEG-CESTARI-manual-iom-guia-consulta-rapida-50111652-pt-en-es-web.pdf>, p. 60 | p. 62).*

For gear units stored **longer than nine months**, the same procedures should be fulfilled prior to their operation. For storage exceeding **two years**, the lubricant must be replaced before commissioning, and the lip seals should also be replaced *(<WEG-CESTARI-manual-iom-guia-consulta-rapida-50111652-pt-en-es-web.pdf>, p. 62).*

---

### 7) What is the relationship between cv and kW?
**Answer:**  
The relationship between horsepower (cv) and kilowatts (kW) is defined as follows:

- **1 cv** is equivalent to approximately **0.736 kW**.  
- Conversely, **1 kW** is equivalent to approximately **1.359 cv**.

This relationship can be expressed in the equations:

- \( P(\text{kW}) = 0.736 \times P(\text{cv}) \)  
- \( P(\text{cv}) = 1.359 \times P(\text{kW}) \)

These conversions indicate that while both units measure power, they are based on different systems of measurement, with cv being more common in some regions such as Brazil, and kW being used internationally. This information is outlined in the document **"WEG-motores-eletricos-guia-de-especificacao-50032749-brochure-portuguese-web.pdf" (page 7).**

---

### 8) Quais são as classes de isolamento citadas e seus limites de temperatura?
**Resposta:**  
As classes de isolamento e seus limites de temperatura, conforme a norma ABNT NBR 17094 e IEC 60034-1, são:

- **Classe A:** 105 °C  
- **Classe E:** 120 °C  
- **Classe B:** 130 °C  
- **Classe F:** 155 °C  
- **Classe H:** 180 °C  

Essas classes são definidas pela maior temperatura que o material ou sistema de isolamento pode suportar continuamente sem afetar sua vida útil, **filename:WEG-motores-eletricos-guia-de-especificacao-50032749-brochure-portuguese-web.pdf, p.35.**

---

### 9) Qual é a fórmula da potência ativa trifásica?
**Resposta:**  
A fórmula da potência ativa trifásica é:

\[
P = 3 \cdot U \cdot I \cdot \cos \varphi
\]

onde:

- \(P\) é a potência ativa (em watts),  
- \(U\) é a tensão entre fases (em volts),  
- \(I\) é a corrente (em amperes),  
- \(\cos \varphi\) é o fator de potência, que leva em consideração a defasagem entre a corrente e a tensão.

---

### 10) O que é o fator de potência e qual sua expressão?
**Resposta:**  
O fator de potência é uma medida da eficiência com que a energia elétrica é convertida em trabalho útil. Ele é representado pela relação entre a **potência ativa (P)**, que realiza trabalho, e a **potência aparente (S)**, que inclui tanto a potência ativa quanto a potência reativa (Q). O fator de potência é geralmente expresso como:

\[
\text{Fator de Potência} = \frac{P}{S} = \cos \phi
\]

onde \(\phi\) é o ângulo de defasagem entre a corrente e a tensão. A potência ativa é medida em watts (W), e a potência aparente em volt-amperes (VA) **filename:WEG-motores-eletricos-guia-de-especificacao-50032749-brochure-portuguese-web.pdf, p. 8.**

---

## 🩺 OCR Fallback

For pages with replacement chars (`�`) or missing Unicode mapping:  
- Detect “low-quality text” → render page to image → run `pytesseract.image_to_string(img, lang="por+eng+spa")`.  
- Merge OCR result into page text before chunking.  
- Track OCR usage via metric `ingest_ocr_pages_total`.

---

## 📊 Metrics & Observability

- **Prometheus endpoint:** `GET /metrics`  
- **UI metrics JSON:** `GET /ui-metrics`  
  - Counters: uploads, duplicates, chunks, OCR pages, embed batches/vectors, Milvus insert batches/errors, queries/errors.  
  - **Stage latency**: parse / chunkify / embed / milvus_insert / search (avg, p50, p90, p99) + **histogram per stage**.  
- **Streamlit → Metrics page:** shows counts, table (avg/p50/p90/p99), and per-stage histograms (multiselect by stage).

---

## 🪵 Logging

- **loguru** across the app (level, time, module:line).  
- Docker:  
```bash
  docker compose logs -f api
  docker compose logs -f ui
  docker compose logs -f milvus
```
---

## 🚀 How to Run

### 0) Prereqs
- Docker Desktop/Engine + Docker Compose.
- Ports to keep free:
    - 2379 (etcd)
    - 9000, 9001 (MinIO)
    - 19530 (Milvus gRPC; REST proxy is also enabled)
    - 9091 (Milvus REST/health)
    - 27017 (Mongo)
    - 8000 (API)
    - 8501 (UI)


### 1) Environment
Create your `.env` from the template and fill keys:

```bash
cp .env.example .env
```
> ATTENTION: Need to provide your own OPENAI_API_KEY

### 2) Bring up the stack
```bash
docker compose up --build
``` 
Wait until:
- Milvus is healthy (/healthz),
- milvus-init finishes (collection/index created and loaded),
- API on :8000, UI on :8501.

### 3) Open the UI
http://localhost:8501

Upload PDFs (sidebar) → Ask questions (main area) → Metrics (sidebar → Metrics).

### 4) Sanity checks
API health
```bash
curl -s http://localhost:8000/healthz
``` 

Milvus REST (list collections)
```bash
curl -s -X POST http://localhost:9091/v2/vectordb/collections/list \
  -H "Content-Type: application/json" -d '{}' | jq
``` 

Describe schema
```bash
curl -s -X POST http://localhost:9091/v2/vectordb/collections/describe \
  -H "Content-Type: application/json" -d '{"collectionName":"doc_chunks"}' | jq
``` 

Metrics
```bash
curl -s http://localhost:8000/metrics | head -n 25
curl -s http://localhost:8000/ui-metrics | jq
``` 

### 5) Stop/Clean
```bash
# stop (preserve volumes)
docker compose down

# full reset (drop data)
docker compose down -v
```

--- 
<!-- ## 🔭 Some Points to Improve (roadmap)

1. **Provider fallback**
   - Add an open-source LLM (e.g., small Qwen/Mistral) if OpenAI is unavailable.
   - Optional: extend to other vendors (Gemini/Anthropic) with automatic failover.

2. **Latency / scale**
   - Split ingestion and serving into separate workers/services.
   - Parallelize multi-file ingestion; use background jobs + progress API.
   - Batch and backpressure controls for embeddings and Milvus inserts.

3. **Evaluation**
   - Provide a small `eval.py` using a “golden set” (these README Q&As).
   - Report retrieval metrics (Recall@k, nDCG@k) and answer coverage vs. confidence.
   - CI job to run eval on PRs touching retrieval.

4. **Multilingual**
   - Language-aware analyzer selection (e.g., portuguese/english) at index and query time.
   - Ensure OCR auto-selects the correct language set (por+eng+spa).
   - Optionally add translation fallback for queries/documents.

5. **S3 integration**
   - Persist original PDFs; store pre-signed URLs in metadata.
   - Streamlit citations link to the exact page of the source document.
 -->


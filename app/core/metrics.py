import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

# Contagens
INGEST_FILES = Counter(
	"ingest_files_total",
	"Arquivos enviados para ingestao",
)

INGEST_DUPLICATES = Counter(
	"ingest_duplicates_total",
	"Arquivos ignorados (hash duplicado)",
)

INGEST_CHUNKS = Counter(
	"ingest_chunks_total",
	"Chunks gerados",
)
INGEST_OCR_PAGES = Counter(
	"ingest_ocr_pages_total",
	"Paginas OCR aplicadas",
)

EMBED_REQUESTS = Counter(
	"embed_requests_total",
	"Chamadas de embedding (batches)",
)
EMBED_VECTORS = Counter(
	"embed_vectors_total",
	"Quantidade de textos embedados",
)

MILVUS_INSERT_BATCHES = Counter(
	"milvus_insert_batches_total", "Batches enviados ao Milvus"
)
MILVUS_INSERT_ERRORS = Counter(
	"milvus_insert_errors_total",
	"Falhas ao inserir",
)

QUERY_REQUESTS = Counter(
	"query_requests_total",
	"Perguntas recebidas",
)
QUERY_ERRORS = Counter(
	"query_errors_total",
	"Erros em resposta de perguntas",
)

SEARCH_REQUESTS = Counter(
	"search_requests_total",
	"Consultas de busca recebidas",
)
SEARCH_ERRORS = Counter(
	"search_errors_total",
	"Erros em consultas de busca",
)

# latências por estágio (segundos)
STAGE_LATENCY = Histogram(
	"rag_stage_latency_seconds",
	"Latencia por estagio do pipeline",
	["stage"],
	# parse | chunkfy | embed | milvus_insert | search_dense | search_sparse | rerank | generate
	buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)


@contextmanager
def observe(stage: str):
	start = time.perf_counter()
	try:
		yield
	finally:
		STAGE_LATENCY.labels(stage).observe(time.perf_counter() - start)

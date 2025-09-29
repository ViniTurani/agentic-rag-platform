from typing import Any, Dict, List, Tuple

from app.core.metrics import (
	EMBED_REQUESTS,
	EMBED_VECTORS,
	INGEST_CHUNKS,
	INGEST_DUPLICATES,
	INGEST_FILES,
	INGEST_OCR_PAGES,
	MILVUS_INSERT_BATCHES,
	MILVUS_INSERT_ERRORS,
	QUERY_ERRORS,
	QUERY_REQUESTS,
	SEARCH_ERRORS,
	SEARCH_REQUESTS,
	STAGE_LATENCY,
)


def _counter_value(c) -> int:
	try:
		return int(c._value.get())  # type: ignore[attr-defined]
	except Exception:
		return 0


def _stage_latency_stats() -> Dict[str, Any]:
	"""Return per-stage histogram stats: count, sum, avg, p50/p90/p99, buckets."""
	result: Dict[str, Any] = {}
	collected = STAGE_LATENCY.collect()
	collected = list(collected)

	if not collected:
		return result

	metric = collected[0]
	# Organize samples by stage
	tmp: Dict[str, Dict[str, Any]] = {}
	for s in metric.samples:
		name: str = s.name  # e.g., rag_stage_latency_seconds_bucket | _sum | _count
		labels = s.labels or {}
		stage = labels.get("stage", "unknown")
		d = tmp.setdefault(stage, {"buckets": []})

		if name.endswith("_bucket"):
			# cumulative bucket; labels has 'le'
			le = labels.get("le", "+Inf")
			try:
				# convert le to float when possible
				le_f = float("inf") if le == "+Inf" else float(le)
			except Exception:
				le_f = float("inf")
			d["buckets"].append((le_f, float(s.value)))
		elif name.endswith("_sum"):
			d["sum"] = float(s.value)
		elif name.endswith("_count"):
			d["count"] = int(s.value)

	# Compute stats
	for stage, d in tmp.items():
		count = int(d.get("count", 0))
		total = float(d.get("sum", 0.0))
		buckets: List[Tuple[float, float]] = sorted(
			d.get("buckets", []), key=lambda x: x[0]
		)

		def pct(q: float):
			if count <= 0 or not buckets:
				return None
			target = q * count
			for le, cum in buckets:
				if cum >= target:
					return None if le == float("inf") else le
			return None

		result[stage] = {
			"count": count,
			"sum": total,
			"avg": (total / count) if count > 0 else None,
			"p50": pct(0.50),
			"p90": pct(0.90),
			"p99": pct(0.99),
			"buckets": [
				{"le": ("+Inf" if le == float("inf") else le), "cumulative": cum}
				for le, cum in buckets
			],
		}

	return result


def get_ui_metrics() -> Dict[str, Any]:
	"""Return metrics for UI consumption."""
	return {
		"counts": {
			"ingest": {
				"files": _counter_value(INGEST_FILES),
				"duplicates": _counter_value(INGEST_DUPLICATES),
				"chunks": _counter_value(INGEST_CHUNKS),
				"ocr_pages": _counter_value(INGEST_OCR_PAGES),
			},
			"embed": {
				"requests": _counter_value(EMBED_REQUESTS),
				"vectors": _counter_value(EMBED_VECTORS),
			},
			"milvus": {
				"insert_batches": _counter_value(MILVUS_INSERT_BATCHES),
				"insert_errors": _counter_value(MILVUS_INSERT_ERRORS),
			},
			"question": {
				"requests": _counter_value(QUERY_REQUESTS),
				"errors": _counter_value(QUERY_ERRORS),
			},
			"search": {
				"requests": _counter_value(SEARCH_REQUESTS),
				"errors": _counter_value(SEARCH_ERRORS),
			},
		},
		"stage_latency": _stage_latency_stats(),
	}

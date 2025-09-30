from __future__ import annotations
import json
from typing import Any
from agents import RunContextWrapper
from loguru import logger

from app.core.pdf_uploader.embedder import AsyncEmbedder
from app.core.connectors.milvus import MilvusSearch

# Busca híbrida semelhante ao seu rag.controllers.hybrid_search
async def kb_retrieve(ctx: RunContextWrapper[Any], args_json: str) -> str:
    """
    Realiza busca híbrida (BM25 + vetor) no Milvus e retorna top_k chunks.
    args: {"query": str, "top_k": int, "sparse_weight": float, "dense_weight": float}
    """
    try:
        args = json.loads(args_json or "{}")
        query = str(args.get("query", "")).strip()
        top_k = int(args.get("top_k", 5))
        sw = float(args.get("sparse_weight", 0.5))
        dw = float(args.get("dense_weight", 0.5))
        if not query:
            return "[]"

        [qvec] = await AsyncEmbedder().encode([query])
        raw = MilvusSearch().search(
            query=query,
            dense_embedding=qvec,
            expr="",
            dense_weight=dw,
            sparse_weight=sw,
            limit=top_k,
        )
        hits = raw.get("data") if isinstance(raw, dict) else raw
        out = []
        if isinstance(hits, list):
            for h in hits[:top_k]:
                if not isinstance(h, dict):
                    continue
                out.append({
                    "text": str(h.get("text") or ""),
                    "source": h.get("source"),
                    "file_id": h.get("file_id"),
                    "page": h.get("page"),
                    "chunk_index": h.get("chunk_index"),
                    "filename": h.get("filename"),
                    "score": h.get("distance"),
                })
        return json.dumps(out, ensure_ascii=False)
    except Exception:
        logger.exception("kb_retrieve failed")
        return "[]"
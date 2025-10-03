import re
from typing import Any, Dict, List

from app.rag.schemas import Chunk

_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_WS_RE = re.compile(r"\s+")


def _strip_md_images(text: str) -> str:
	# remove markdown images like ![alt](url)
	return _MD_IMG_RE.sub("", text or "")


def _unhyphenate(text: str) -> str:
	# join words: "inter-\ncaçao"->"interaçao"
	text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text or "")
	return text.replace("\r", "")


def _normalize_ws(text: str) -> str:
	# collapse whitespace/newlines to single spaces
	return _WS_RE.sub(" ", (text or "")).strip()


def _sentence_split(text: str) -> List[str]:
	"""
	Lightweight sentence splitter for PT/EN/ES.
	Swap for nltk/pysbd/spacy later without changing callers.
	"""
	parts = re.split(r"(?<=[\.!?…])\s+(?=[^\s])", text)
	out = [p.strip() for p in parts if p and p.strip()]
	return out if out else [text]


def _chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
	"""
	Token-agnostic, sentence-aware chunking with small char overlap.
	"""
	text = _normalize_ws(_strip_md_images(_unhyphenate(text)))
	if not text:
		return []
	if len(text) <= 500:  # tiny page = one chunk
		return [text]

	sents: list[str] = _sentence_split(text)
	chunks, cur = [], ""
	for s in sents:
		if not cur:
			cur = s
			continue
		if len(cur) + 1 + len(s) <= max_chars:
			cur = f"{cur} {s}"
		else:
			chunks.append(cur)
			tail = cur[-overlap:] if overlap > 0 else ""
			cur = (tail + " " + s).strip()
	if cur:
		chunks.append(cur)
	return [c for c in chunks if c]


def add_extra_info(text: str, **info: Any) -> str:
	extras = " ".join(f"[{k}:{v}]" for k, v in info.items() if v is not None)
	return f"{text} {extras}".strip() if extras else text


def chunkfy_pages(
	pages: List[Dict[str, Any]],
	file_id: str,
	filename: str | None,
	title: str | None = None,
	max_chars: int = 1200,
	overlap: int = 150,
) -> List[Chunk]:
	"""
	Input: pages like those from pymupdf4llm.to_markdown(page_chunks=True),
		e.g. [{"page": 1, "text": "...markdown..."}, ...]
	Output: list of objects ready for your MilvusInsert.upload_chunks()
	"""
	chunks: List[Chunk] = []
	for i, p in enumerate(pages, start=1):
		page_no = int(p.get("page") or p.get("number") or i)
		text = p.get("text") or p.get("content") or (p if isinstance(p, str) else "")
		parts = _chunk_text(text, max_chars=max_chars, overlap=overlap)

		for idx, ch in enumerate(parts):
			ch = add_extra_info(
				ch, filename=filename, page_number=page_no, file_id=file_id, title=title
			)
			chunks.append(
				Chunk(
					title=title,
					filename=filename if filename else "N/A",
					page_idx=page_no,
					chunk_idx=idx,
					text=ch,
					source=(
						f"{filename}#p{page_no}#{idx}"
						if filename
						else f"file#{file_id}#p{page_no}#{idx}"
					),
				)
			)
	return chunks

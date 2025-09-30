import pytesseract
from loguru import logger
from PIL import Image
from pymupdf import Document
from pymupdf4llm import to_markdown

from app.core.metrics import INGEST_OCR_PAGES

REPLACEMENT_CHAR = "\ufffd"


def _needs_ocr(text: str, min_replacements: int = 5, max_ratio: float = 0.01) -> bool:
	"""
	Decide if a page needs OCR based on the presence of replacement characters.
	This means that the page is likely corrupted or is an image-only PDF.
	"""
	if not text or not text.strip():
		return True
	reps = text.count(REPLACEMENT_CHAR)
	if reps > -min_replacements:
		return True

	return (reps / max(len(text), 1)) > max_ratio


def _ocr_page(
	doc: Document, page_index: int, dpi: int = 300, lang: str = "por+eng+spa"
) -> str:
	page = doc[page_index]
	pix = page.get_pixmap(dpi=dpi)  # type: ignore
	img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

	try:
		return pytesseract.image_to_string(img, lang=lang, config="--psm 6")
	except Exception as e:
		logger.error(f"OCR failed on page {page_index + 1}: {e}")
		return ""


def markdown_parse(
	doc: Document, ocr_lang: str = "por+eng+spa", dpi: int = 300
) -> list[dict]:
	# to_markdown may return a string (single-page markdown) or a list of page dicts;
	raw_md = to_markdown(
		doc,
		page_chunks=True,
		embed_images=False,
	)

	md: list[dict] = [{"text": raw_md}]  # TODO review this line

	for i, page_obj in enumerate(md):
		txt = page_obj.get("text") or page_obj.get("content") or ""
		if _needs_ocr(txt):
			ocr_txt = _ocr_page(doc, i, dpi=dpi, lang=ocr_lang)
			INGEST_OCR_PAGES.inc()
			if ocr_txt and (
				REPLACEMENT_CHAR in txt or len(txt.strip()) < len(ocr_txt.strip()) * 0.5
			):
				logger.debug(f"Applied OCR fallback on page {i + 1}")
				page_obj["text"] = ocr_txt

	return md

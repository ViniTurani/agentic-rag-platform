from pydantic import BaseModel


class File(BaseModel):
	file_hash: str
	filename: str | None
	title: str | None
	content: str
	total_pages: int
	size_bytes: int
	mime: str


class Chunk(BaseModel):
	filename: str
	title: str | None
	page_idx: int
	chunk_idx: int
	source: str
	text: str


class FailedChunk(BaseModel):
	chunk: Chunk
	filename: str | None
	error: str


class UploadResponse(BaseModel):
	message: str
	documents_indexed: int
	total_chunks: int
	failed_chunks: list[FailedChunk]
	failed_files: list[str] | None = None


class EmbeddedChunk(Chunk):
	vector: list[float]


class IndexingResult(BaseModel):
	message: str
	total_chunks: int
	errors: list[FailedChunk]
	inserted_file_id: str | None = None
	inserted_chunk_ids: list[str] | None = None


class SearchResult(BaseModel):
	text: str
	source: str | None = None
	file_id: str | None = None
	filename: str | None = None
	page: int | None = None
	chunk_index: int | None = None
	score: float | None = None

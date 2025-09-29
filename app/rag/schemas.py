from pydantic import BaseModel


class FailedChunk(BaseModel):
    chunk_id: str
    filename: str | None
    error: str


class UploadResponse(BaseModel):
    message: str
    documents_indexed: int
    total_chunks: int
    failed_chunks: list[FailedChunk]
    failed_files: list[str] | None = None


class Chunk(BaseModel):
    chunk_id: str
    file_id: str
    filename: str
    title: str | None
    page_idx: int
    chunk_idx: int
    source: str
    text: str


class EmbeddedChunk(Chunk):
    vector: list[float]


class IndexingResult(BaseModel):
    message: str
    total_chunks: int
    errors: list[FailedChunk]
    inserted_file_id: str | None = None


class QuestionRequest(BaseModel):
    question: str


class QuestionResponse(BaseModel):
    answer: str
    references: list[str]


class SearchResult(BaseModel):
    text: str
    source: str | None = None
    file_id: str | None = None
    filename: str | None = None
    page: int | None = None
    chunk_index: int | None = None
    score: float | None = None

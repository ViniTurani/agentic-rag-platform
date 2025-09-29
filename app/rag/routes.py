from fastapi import APIRouter, UploadFile
from pathlib import Path


from .controllers import (
    hybrid_search,
    upload_pdf_documents,
)
from .schemas import (
    Chunk,
    UploadResponse,
)

router = APIRouter()

@router.get("/hybrid_search")
async def search_hybrid_search(
    query: str,
    top_k: int = 3,
    sparse_weight: float = 0.5,
    dense_weight: float = 0.5,
):
    return await hybrid_search(
        query=query,
        sparse_weight=sparse_weight,
        dense_weight=dense_weight,
        top_k=top_k,
    )

@router.post("/chunks", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile]):
    return await upload_pdf_documents(files)

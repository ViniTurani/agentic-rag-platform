from app.rag.models import FileDAO, ChunkDAO
from app.core.connectors.mongo import MongoHelper

mongo_client = MongoHelper()


def delete_file_and_chunks(file_id: str):
    mongo_client.delete_one(model=FileDAO, filt={"file_id": file_id})
    mongo_client.delete_many({"file_id": file_id}, model=ChunkDAO)

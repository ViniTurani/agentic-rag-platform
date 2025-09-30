from app.core.connectors.mongo import MongoHelper
from app.rag.models import ChunkDAO

mongo_client = MongoHelper()


def delete_file_and_chunks(file_id: str):
	mongo_client.delete_many({"file_id": file_id}, model=ChunkDAO)

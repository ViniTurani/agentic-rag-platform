from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
	# openai
	OPENAI_API_KEY: str

	# milvus stuff
	MILVUS_URL: str
	MILVUS_SECRET: str
	MILVUS_COLLECTION: str

	# fastapi
	HOST: str = "0.0.0.0"
	PORT: int = 8000
	RELOAD: bool = True
	WORKERS: int = 1
	AGENTS_CONFIG_PATH: str = "resources/agents.yaml"

	# mongo
	MONGO_URI: str
	MONGO_DB: str

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"

	@classmethod
	@lru_cache
	def get(cls) -> "Settings":
		return Settings()  # type: ignore

import asyncio
from typing import List

from openai import OpenAI

from app.core.metrics import EMBED_REQUESTS, EMBED_VECTORS, observe
from app.settings import Settings

setts = Settings.get()


class AsyncEmbedder:
	def __init__(
		self,
		model_name: str = "text-embedding-3-small",
		batch_size: int = 32,
	):
		self.client = OpenAI(api_key=setts.OPENAI_API_KEY)
		self.model_name = model_name
		self.batch_size = batch_size

	async def encode(self, texts: List[str]) -> List[List[float]]:
		"""Encode a list of texts off the event loop."""
		EMBED_REQUESTS.inc()
		EMBED_VECTORS.inc(len(texts))

		loop = asyncio.get_running_loop()

		def _encode(batch):
			with observe("embed"):
				resp = self.client.embeddings.create(input=batch, model=self.model_name)
			return [d.embedding for d in resp.data]

		return await loop.run_in_executor(None, _encode, texts)

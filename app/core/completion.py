import asyncio
import json
from typing import Any, Dict, List

from loguru import logger
from openai import OpenAI

from app.core.connectors.milvus import MilvusSearch
from app.core.pdf_uploader.embedder import AsyncEmbedder
from app.rag.schemas import QuestionResponse, SearchResult
from app.settings import Settings


class OpenAIToolCalling:
	"""Lightweight helper around OpenAI Responses API with tool-calling.

	Exposes a single public method `answer_with_retrieval` that:
	- Presents a tool to the model (hybrid_search) to fetch relevant context
	- Lets the model optionally rephrase the user query before calling the tool
	- Submits tool outputs back to the model and returns the final answer
	- Also returns the references (texts) used for the answer
	"""

	def __init__(self, model: str = "gpt-4o-mini"):
		sets = Settings.get()
		self.client = OpenAI(api_key=sets.OPENAI_API_KEY)
		self.model = model

	def _tool_schema(self) -> List[Dict[str, Any]]:
		return [
			{
				"type": "function",
				"name": "hybrid_search",
				"description": (
					"Retrieve relevant passages from the document index using hybrid "
					"(dense + sparse - this can be set using `sparse_weight` and `dense_weight`) "
					"search. Provide a clear, search-optimized query."
				),
				"parameters": {
					"type": "object",
					"properties": {
						"query": {
							"type": "string",
							"description": "User question rewritten into a search-friendly query.",
						},
						"sparse_weight": {
							"type": "number",
							"description": "Sparse weight for hybrid search.",
							"enum": [0.5, 0.4, 1],
							"default": 0.5,
						},
						"dense_weight": {
							"type": "number",
							"description": "Dense weight for hybrid search.",
							"enum": [0.5, 0.6, 1],
							"default": 0.5,
						},
						"top_k": {
							"type": "number",
							"description": "Number of top results to return.",
							"default": 5,
						},
					},
					"required": ["query", "sparse_weight", "dense_weight", "top_k"],
				},
			}
		]

	def answer_with_retrieval(self, user_question: str) -> QuestionResponse:
		"""Run an answer flow where the model can call a hybrid_search tool.

		Returns: (answer, references)
		"""
		system = """You are a precise RAG assistant.

	Workflow:
	1) First call the `hybrid_search` tool with the user's question (and any file hints) to fetch context.
	2) Answer **only** using the retrieved context-never use outside knowledge.

	Citations (mandatory):
	- Every factual statement must be supported by the provided context.
	- Append a citation in this exact format at the end of the relevant sentence: "..., <filename>, p.<page>." If multiple sources are needed, separate with " | " (max 3).
	- Use the retrieved fields `filename` (base name only) and `page` (omit page if not present). Do not invent filenames or pages.

	Document selection rules:
	- Always consider the **document title** to disambiguate intent.
	- If the user asks for a specific file, **use content from that file only**, even if other chunks look relevant.
	- When multiple documents are retrieved, prefer chunks whose titles best match the question.

	Answer style:
	- Be concise, factual, and structured (short paragraphs or bullet points when helpful).
	- Preserve units, values, and wording from the source when precision matters.
	- If the context is insufficient or conflicting, say so explicitly and request clarification or the relevant file.
	- Respond in the same language as the user's question.

	Prohibitions:
	- Do not cite anything beyond the provided context.
	"""
		input_list = [
			{"role": "system", "content": system},
			{"role": "user", "content": user_question},
		]

		# 1) Initial response request with tools available
		resp = self.client.responses.create(
			model=self.model,
			input=input_list,  # type: ignore
			tools=self._tool_schema(),  # type: ignore
		)
		tool_called = False

		input_list += resp.output
		references: List[str] = []

		for item in resp.output:
			if item.type == "function_call":
				if item.name == "hybrid_search":
					tool_called = True
					args = json.loads(item.arguments)
					query: str = args.get("query") or user_question
					sparse_weight: float = float(args.get("sparse_weight", 0.5))
					dense_weight: float = float(args.get("dense_weight", 0.5))
					top_k: int = int(args.get("top_k", 5))

					logger.debug(
						f"Calling hybrid search with query: {query},\n"
						f"Sparse_weight: {sparse_weight},\n"
						f"Dense_weight: {dense_weight},\n"
						f"Top_k: {top_k}"
					)

					# Run our retrieval (async) and format results for the model
					retrieval_error = None
					try:
						results: List[SearchResult] = asyncio.run(
							hybrid_search(
								query=query,
								sparse_weight=sparse_weight,
								dense_weight=dense_weight,
								top_k=top_k,
							)
						)
					except Exception as e:
						retrieval_error = str(e)
						logger.error(f"Error during hybrid search: {str(e)}")
						results = []

					references = [r.text for r in results]
					input_list.append(
						{
							"type": "function_call_output",
							"call_id": item.call_id,
							"output": (
								json.dumps(
									[
										{
											"text": r.text,
											"source": r.source,
											"filename": r.filename,
											"file_id": r.file_id,
											"page": r.page,
											"chunk_index": r.chunk_index,
											"score": r.score,
										}
										for r in results
									]
								)
								if results
								else (
									f"Something went wrong during retrieval."
									f" Error: {retrieval_error}"
								)
							),
						}
					)

		if not tool_called:
			logger.debug("No tool was called by the model.")
			return QuestionResponse(
				answer=resp.output_text.strip() if resp.output_text else "",
				references=[],
			)

		# call the model with no tool calls
		resp = self.client.responses.create(
			model=self.model,
			instructions=(
				"Based on the retrieved information, provide a concise response."
				" ALWAYS reference the source of the information, just like this: \n"
				"This is the answer, as it appears on:"
				" file <filename>, page <page> and chunk number <chunk_index>."
			),
			input=input_list,  # type: ignore
		)
		return QuestionResponse(
			answer=resp.output_text.strip() if resp.output_text else "",
			references=references,
		)

from __future__ import annotations

from typing import List, Optional

from loguru import logger
from openai.types.responses import EasyInputMessageParam

from agents import ModelSettings, RunConfig, Runner, RunResult, trace
from app.settings import Settings

from .loader import build_agents, build_tools, load_config


class SwarmEngine:
	def __init__(self, cfg_path: str, workflow_name: str = "agentic_rag_swarm") -> None:
		self.cfg = load_config(path=cfg_path)
		self.tools = build_tools(cfg=self.cfg)
		self.agents = build_agents(cfg=self.cfg, tools_by_name=self.tools)
		self.entry = self.agents[self.cfg.entry_agent]
		self.workflow_name = workflow_name

	async def run(
		self,
		messages: List[EasyInputMessageParam],
		user_id: str,
		thread_id: Optional[str] = None,
		run_overrides: Optional[ModelSettings] = None,
	) -> RunResult:
		try:
			run_config = (
				RunConfig(model_settings=run_overrides)
				if run_overrides
				else RunConfig()
			)
		except Exception:
			logger.critical(
				"Failed to parse run_overrides into RunConfig, using defaults; "
				f"user={user_id}, thread={thread_id}, overrides={run_overrides}"
			)
			run_config = RunConfig()

		with trace(workflow_name=self.workflow_name):
			logger.debug(f"Starting run for user={user_id} thread={thread_id}")
			result = await Runner.run(
				self.entry,
				messages,  # type: ignore
				run_config=run_config,
				max_turns=self.cfg.model_defaults.max_turns,
			)
		return result


_engine_singleton: Optional[SwarmEngine] = None


def get_engine() -> SwarmEngine:
	global _engine_singleton
	if _engine_singleton is None:
		logger.info("Initializing new SwarmEngine")
		s = Settings.get()
		_engine_singleton = SwarmEngine(
			cfg_path=getattr(s, "AGENTS_CONFIG_PATH", "resources/agents.yaml")
		)
	return _engine_singleton

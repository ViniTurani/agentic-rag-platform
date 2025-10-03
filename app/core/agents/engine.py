from typing import Optional

from loguru import logger

from agents import ModelSettings, RunConfig, Runner, RunResult, SQLiteSession, trace
from app.settings import Settings

from .loader import build_agents, build_tools, load_config


class SwarmEngine:
	def __init__(self, cfg_path: str, workflow_name: str = "agentic_rag_swarm") -> None:
		self.cfg = load_config(cfg_path)
		self.tools = build_tools(self.cfg)
		self.agents = build_agents(self.cfg, self.tools)
		self.entry = self.agents[self.cfg.entry_agent]
		self.workflow_name = workflow_name

	async def run(
		self,
		message: str,
		user_id: str,
		thread_id: Optional[str] = None,
		run_overrides: Optional[ModelSettings] = None,
	) -> RunResult:
		session = SQLiteSession(thread_id or f"swarm:{user_id}")
		try:
			if run_overrides:
				run_config = RunConfig(model_settings=run_overrides)
			else:
				run_config = RunConfig()
		except Exception:
			logger.critical(
				"Failed to parse run_overrides into RunConfig, using defaults",
				f"For user {user_id}, session {thread_id}, overrides: {run_overrides}",
			)

		with trace(workflow_name=self.workflow_name, group_id=session.session_id):
			logger.debug(
				f"Starting run for user {user_id}, session {session.session_id}, "
			)
			result = await Runner.run(
				self.entry,
				message,
				session=session,
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

from typing import Any, Optional, cast

from agents import RunConfig, Runner, SQLiteSession, trace
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
		session_id: Optional[str] = None,
		run_overrides: Optional[dict[str, Any]] = None,
	):
		session = SQLiteSession(session_id or f"swarm:{user_id}")
		# Merge overrides with defaults into a plain dict first
		run_config_dict = (run_overrides or {}) | {
			"model_settings": {"temperature": self.cfg.model_defaults.temperature},
			"max_turns": self.cfg.model_defaults.max_turns,
		}
		# Try to construct a RunConfig instance; if that fails, fall back to casting
		try:
			run_config = RunConfig(**run_config_dict)  # type: ignore[arg-type]
		except Exception:
			run_config = cast(RunConfig, run_config_dict)
		with trace(workflow_name=self.workflow_name, group_id=session.session_id):
			result = await Runner.run(
				self.entry, message, session=session, run_config=run_config
			)
		return result


_engine_singleton: Optional[SwarmEngine] = None


def get_engine() -> SwarmEngine:
	global _engine_singleton
	if _engine_singleton is None:
		s = Settings.get()
		_engine_singleton = SwarmEngine(
			cfg_path=getattr(s, "AGENTS_CONFIG_PATH", "resources/agents.yaml")
		)
	return _engine_singleton

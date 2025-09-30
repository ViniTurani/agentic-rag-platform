from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict

import yaml

from agents import Agent, FileSearchTool, FunctionTool, WebSearchTool, handoff

from .config_schema import AgentsConfigSchema

HOSTED_TOOL_MAP = {
	"WebSearchTool": WebSearchTool,
	"FileSearchTool": FileSearchTool,
}


def _expand_env(obj: Any) -> Any:
	if isinstance(obj, dict):
		return {k: _expand_env(v) for k, v in obj.items()}
	if isinstance(obj, list):
		return [_expand_env(v) for v in obj]
	if isinstance(obj, str):
		return os.path.expandvars(obj)
	return obj


def load_config(path: str | Path) -> AgentsConfigSchema:
	data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
	return AgentsConfigSchema.model_validate(_expand_env(data))


def _import_obj(dotted: str) -> Any:
	mod, _, attr = dotted.partition(":")
	if not attr:
		mod, _, attr = dotted.rpartition(".")
	return getattr(importlib.import_module(mod), attr)


def build_tools(cfg: AgentsConfigSchema) -> Dict[str, Any]:
	tools: Dict[str, Any] = {}
	for t in cfg.tools:
		if t.kind == "hosted":
			cls = HOSTED_TOOL_MAP[t.type]  # type: ignore[index]
			tools[t.name] = cls(**(t.config or {}))
		elif t.kind == "python_function":
			if not t.dotted_path:
				raise ValueError(
					f"python_function tool '{t.name}' is missing a dotted_path"
				)
			tools[t.name] = _import_obj(t.dotted_path)
		elif t.kind == "custom_json_schema":
			if not t.implementation:
				raise ValueError(
					f"custom_json_schema tool '{t.name}' "
					"is missing an implementation dotted path"
				)
			impl = _import_obj(t.implementation)
			tools[t.name] = FunctionTool(
				name=t.name,
				description=(impl.__doc__ or f"{t.name} tool").strip(),
				params_json_schema=t.schema or {},
				on_invoke_tool=impl,
			)
		else:
			raise ValueError(f"Invalid tool kind: {t.kind}")
	return tools


def build_agents(
	cfg: AgentsConfigSchema, tools_by_name: Dict[str, Any]
) -> Dict[str, Agent]:
	agents: Dict[str, Agent] = {}
	for a in cfg.agents:
		prompt = Path(a.prompt_file).read_text(encoding="utf-8")
		tool_objs = [tools_by_name[n] for n in a.tool_refs]
		agents[a.name] = Agent(name=a.name, instructions=prompt, tools=tool_objs)

	for a in cfg.agents:
		if not a.handoffs:
			continue
		current = agents[a.name]
		handoff_tools = [handoff(agent=agents[dest]) for dest in a.handoffs]
		agents[a.name] = Agent(
			name=current.name,
			instructions=current.instructions,
			tools=current.tools,
			handoffs=handoff_tools,
		)
	return agents

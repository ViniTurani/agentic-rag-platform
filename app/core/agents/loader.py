import importlib
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from loguru import logger
from pydantic import BaseModel

from agents import Agent, FileSearchTool, FunctionTool, WebSearchTool
from app.core.utils import get_json_schema

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


def _import_obj(
	dotted: str, class_name: str = "Arguments"
) -> Tuple[Any, type[BaseModel]]:
	# Split the path at ':' if present (module:function)
	mod, _, attr = dotted.partition(":")
	if not attr:
		# Otherwise split at the last dot (module.function)
		mod, _, attr = dotted.rpartition(".")

	# Import the module and get the function
	module = importlib.import_module(mod)
	imported_obj = getattr(module, attr) if attr else module

	# Get the Arguments class from the same module
	arguments = getattr(module, class_name)
	if not arguments or not issubclass(arguments, BaseModel):
		raise ValueError(f"Could not find valid {class_name} class in module {mod}")

	return (imported_obj, arguments)


def build_tools(cfg: AgentsConfigSchema) -> Dict[str, Any]:
	tools: Dict[str, Any] = {}
	for t in cfg.tools:
		if t.kind == "hosted":
			logger.debug(f"Building hosted tool: {t.name}")
			if not t.type:
				raise ValueError(f"hosted tool '{t.name}' is missing a type")

			cls = HOSTED_TOOL_MAP.get(t.type)
			if cls is None:
				raise ValueError(f"Unknown hosted tool type '{t.type}'")

			tools[t.name] = cls(**(t.config or {}))

		elif t.kind == "python_function":
			logger.debug(f"Building python_function tool: {t.name}")
			if not t.dotted_path:
				raise ValueError(
					f"python_function tool '{t.name}' is missing a dotted_path"
				)

			impl, arguments = _import_obj(t.dotted_path, "Arguments")

			json_schema = get_json_schema(arguments)

			tools[t.name] = FunctionTool(
				name=t.name,
				description=(impl.__doc__ or f"{t.name} tool").strip(),
				params_json_schema=json_schema,
				on_invoke_tool=impl,
			)

		else:
			logger.error(f"Invalid tool kind: {t.kind}")
			raise ValueError(f"Invalid tool kind: {t.kind}")
	return tools


def build_agents(
	cfg: AgentsConfigSchema,
	tools_by_name: Dict[str, Any],
) -> Dict[str, Agent]:
	agents: Dict[str, Agent] = {}

	# First pass: create Agent objects without resolving handoffs (use empty list)
	for a in cfg.agents:
		logger.debug(f"Building agent: {a.name}")
		prompt = Path(a.prompt_file).read_text(encoding="utf-8")
		tool_objs = [tools_by_name[n] for n in a.tool_refs]
		agents[a.name] = Agent(
			name=a.name,
			instructions=prompt,
			tools=tool_objs,
			handoffs=[],
			handoff_description=a.handoff_description,
		)

	# Second pass: resolve handoffs (strings -> Agent objects or keep Handoff objects)
	for a in cfg.agents:
		raw_handoffs = a.handoffs or []
		resolved: list[Any] = []
		for ref in raw_handoffs:
			if isinstance(ref, str):
				target = agents.get(ref)
				if target is None:
					raise ValueError(
						f"Handoff target '{ref}' for agent '{a.name}' not found"
					)
				resolved.append(target)
			else:
				# Already an Agent or a Handoff object; append as-is
				resolved.append(ref)
		agents[a.name].handoffs = resolved

	return agents

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ToolKind = Literal["hosted", "python_function", "custom_json_schema"]


class ModelDefaultsSchema(BaseModel):
	provider: str = "openai"
	model: str = "gpt-4o-mini"
	temperature: float = 0.2
	max_turns: int = 8


class ToolDefSchema(BaseModel):
	name: str
	kind: ToolKind
	type: Optional[str] = None
	config: Dict[str, Any] = Field(default_factory=dict)
	dotted_path: Optional[str] = None


class AgentDefSchema(BaseModel):
	name: str
	prompt_file: str
	tool_refs: List[str] = Field(default_factory=list)
	handoffs: List[str] = Field(default_factory=list)
	handoff_description: str


class AgentsConfigSchema(BaseModel):
	model_defaults: ModelDefaultsSchema = Field(default_factory=ModelDefaultsSchema)
	entry_agent: str
	tools: List[ToolDefSchema]
	agents: List[AgentDefSchema]

	def tool_by_name(self) -> Dict[str, ToolDefSchema]:
		return {t.name: t for t in self.tools}

	def agent_by_name(self) -> Dict[str, AgentDefSchema]:
		return {a.name: a for a in self.agents}

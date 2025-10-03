from typing import Any

from pydantic import BaseModel


def get_json_schema(base_model: type[BaseModel]) -> dict[str, Any]:
	j_schema = base_model.model_json_schema()
	j_schema["additionalProperties"] = False

	if "$defs" in j_schema:
		for k, v in j_schema["$defs"].items():
			v["additionalProperties"] = False

	return j_schema

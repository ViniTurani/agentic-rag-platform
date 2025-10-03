from collections.abc import MutableMapping
from datetime import datetime, timedelta, timezone
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now_utc() -> datetime:
	return datetime.now(timezone.utc)


class TimestampingMixin(BaseModel):
	"""
	Mixin que adiciona `created_at` e `updated_at` (timezone-aware, UTC) e mantem
	updated_at coerente.

	- Ao inicializar, se nao houver created_at, usa now_utc(); se nao houver updated_at,
	usa o mesmo valor.
	- Ao setar qualquer atributo, se mudar algo que nao seja updated_at, atualiza
	updated_at automaticamente.
	- Garante created_at <= updated_at.
	- Exige que os datetimes sejam timezone-aware em UTC.
	"""

	created_at: datetime = Field(default_factory=now_utc)
	updated_at: datetime = Field(default_factory=now_utc)

	model_config = ConfigDict(validate_assignment=True)

	@model_validator(mode="before")
	@classmethod
	def _init_timestamps(cls, values: dict[str, Any]) -> dict[str, Any]:
		if not isinstance(values, MutableMapping):
			return values
		ts = values.get("created_at") or now_utc()
		values.setdefault("created_at", ts)
		if "updated_at" not in values:
			values.setdefault("updated_at", ts)
		return values

	@model_validator(mode="after")
	def _check_timestamp_order(self) -> Self:
		if self.created_at and self.updated_at and self.created_at > self.updated_at:
			raise ValueError("`created_at` must be <= `updated_at`")
		return self

	@field_validator("created_at", "updated_at", mode="after")
	@classmethod
	def _ensure_aware_utc(cls, dt: datetime) -> datetime:
		"""Ensures that the datetime is timezone-aware and in UTC."""
		if dt.tzinfo is None:
			# fallback para legados
			return dt.replace(tzinfo=timezone.utc)
		if dt.utcoffset() != timedelta(0):
			# normaliza para UTC mantendo o instante
			return dt.astimezone(timezone.utc)
		return dt

	def __setattr__(self, name: str, value: Any) -> None:
		# atualiza updated_at automaticamente em mudanças
		if name == "created_at":
			current_updated_at = getattr(self, "updated_at", None)
			if value and current_updated_at and current_updated_at > value:
				super().__setattr__("updated_at", now_utc())
			else:
				super().__setattr__("updated_at", value)
		elif name != "updated_at" and getattr(self, name, None) != value:
			super().__setattr__("updated_at", now_utc())
		super().__setattr__(name, value)

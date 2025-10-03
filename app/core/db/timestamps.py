from collections.abc import MutableMapping
from datetime import datetime, timedelta, timezone
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now_utc() -> datetime:
	return datetime.now(timezone.utc)


class TimestampingMixin(BaseModel):
	"""
	Mixin that adds `created_at` and `updated_at` (timezone-aware, UTC) and keeps
		`updated_at` consistent.

	- On initialization, if there is no `created_at`, uses now_utc(); if there is no
	`updated_at`, uses the same value.
	- When setting any attribute, if something changes other than `updated_at`,
		`updated_at` is updated automatically.
	- Ensures `created_at` <= `updated_at`.
	- Requires datetimes to be timezone-aware in UTC.
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
			# fallback for legacy values
			return dt.replace(tzinfo=timezone.utc)
		if dt.utcoffset() != timedelta(0):
			# normalize to UTC preserving the instant
			return dt.astimezone(timezone.utc)
		return dt

	def __setattr__(self, name: str, value: Any) -> None:
		# automatically update updated_at on changes
		if name == "created_at":
			current_updated_at = getattr(self, "updated_at", None)
			if value and current_updated_at and current_updated_at > value:
				super().__setattr__("updated_at", now_utc())
			else:
				super().__setattr__("updated_at", value)
		elif name != "updated_at" and getattr(self, name, None) != value:
			super().__setattr__("updated_at", now_utc())
		super().__setattr__(name, value)

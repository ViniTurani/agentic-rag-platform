from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
	user_id: str
	name: str | None = None
	email: str | None = None
	plan: str | None = None


class AccountBase(BaseModel):
	user_id: str
	currency: Literal["BRL"] = "BRL"
	balance_cents: int = 0
	holds_cents: int = 0


class ComplianceBase(BaseModel):
	user_id: str
	kyc_status: Literal["pending", "verified", "rejected"] = "pending"
	risk_score: int = 0
	transfer_enabled: bool = False
	transfer_block_reason: str | None = None


class SecurityBase(BaseModel):
	user_id: str
	login_disabled: bool = False
	failed_attempts: int = 0
	last_login_at: datetime | None = None
	two_factor_enabled: bool = False


class TicketBase(BaseModel):
	ticket_id: str
	user_id: str
	subject: str
	description: str
	status: Literal["open", "pending", "closed"] = "open"


# Saídas tipadas (para tools e APIs)
class CustomerOut(CustomerBase):
	created_at: datetime
	updated_at: datetime


class AccountOut(AccountBase):
	created_at: datetime
	updated_at: datetime


class ComplianceOut(ComplianceBase):
	created_at: datetime
	updated_at: datetime


class SecurityOut(SecurityBase):
	created_at: datetime
	updated_at: datetime


class TicketCreate(BaseModel):
	user_id: str
	subject: str
	description: str


class TicketOut(TicketBase):
	id: str
	created_at: datetime
	updated_at: datetime


class SupportOverview(BaseModel):
	user: CustomerOut | None = None
	account: AccountOut | None = None
	compliance: ComplianceOut | None = None
	security: SecurityOut | None = None
	open_tickets: list[TicketOut] = Field(default_factory=list)

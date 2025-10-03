import pymongo
from beanie import Document

from app.core.db.timestamps import TimestampingMixin

from .schemas import (
	AccountBase,
	ComplianceBase,
	CustomerBase,
	SecurityBase,
	TicketBase,
)


class CustomerDAO(CustomerBase, TimestampingMixin, Document):
	class Settings:
		name = "customers"
		indexes = [
			pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
			pymongo.IndexModel([("updated_at", pymongo.DESCENDING)]),
		]


class AccountDAO(AccountBase, TimestampingMixin, Document):
	class Settings:
		name = "accounts"
		indexes = [
			pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
			pymongo.IndexModel([("updated_at", pymongo.DESCENDING)]),
		]


class ComplianceDAO(ComplianceBase, TimestampingMixin, Document):
	class Settings:
		name = "compliance"
		indexes = [
			pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
			pymongo.IndexModel([("updated_at", pymongo.DESCENDING)]),
		]


class SecurityDAO(SecurityBase, TimestampingMixin, Document):
	class Settings:
		name = "security"
		indexes = [
			pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
			pymongo.IndexModel([("updated_at", pymongo.DESCENDING)]),
		]


class TicketDAO(TicketBase, TimestampingMixin, Document):
	class Settings:
		name = "tickets"
		indexes = [
			pymongo.IndexModel([("ticket_id", pymongo.ASCENDING)], unique=True),
			pymongo.IndexModel([("user_id", pymongo.ASCENDING)]),
			pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
			pymongo.IndexModel([("status", pymongo.ASCENDING)]),
		]

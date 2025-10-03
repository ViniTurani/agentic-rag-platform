import pymongo
from beanie import Document

from app.core.db.timestamps import TimestampingMixin

from .schemas import CustomerBase, TicketBase


class CustomerDAO(CustomerBase, TimestampingMixin, Document):
	class Settings:
		name = "customers"
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
		]

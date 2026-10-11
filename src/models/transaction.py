from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.account import Account
from models.base import Base


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String(30), nullable=False)
    account_out_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=False)
    account_in_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=True)
    value = Column(Numeric(15, 2), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    request_hash = Column(CHAR(64), nullable=False)
    related_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transaction.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_out_id", "idempotency_key"),
        UniqueConstraint("related_transaction_id"),
    )

    DEPOSIT = "DEPOSIT"
    TRANSFER = "TRANSFER"
    FEE = "FEE"
    PAYMENT = "PAYMENT"
    BOX_RETENTION = "BOX_RETENTION"
    BOX_RELEASE = "BOX_RELEASE"
    BOX_WITHDRAWAL = "BOX_WITHDRAWAL"

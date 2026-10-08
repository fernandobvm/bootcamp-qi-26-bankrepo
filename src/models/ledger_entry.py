from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.account import Account
from models.base import Base
from models.transaction import Transaction


class LedgerEntry(Base):
    """Um lançamento numa conta. É daqui que o extrato e a renda do dia saem."""

    __tablename__ = "ledger_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    transaction_id = Column(UUID(as_uuid=True), ForeignKey(Transaction.id), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=False)
    direction = Column(String(10), nullable=False)
    value = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    DEBITO = "DEBITO"
    CREDITO = "CREDITO"

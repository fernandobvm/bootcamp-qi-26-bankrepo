from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.account import Account
from models.base import Base


class Transaction(Base):
    """Uma operação financeira; os lançamentos dela moram em `ledger_entry`.

    Nas operações da caixinha (`BOX_*`), `account_out_id` é sempre a conta
    dona da caixinha e `account_in_id` fica nulo: o dinheiro não sai do
    cliente, só troca de bolso. É isso que deixa a chave de idempotência
    valer por conta — `UNIQUE(account_out_id, idempotency_key)`.
    """

    __tablename__ = "transaction"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String(30), nullable=False)
    account_out_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=False)
    account_in_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=True)
    value = Column(Numeric(15, 2), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    request_hash = Column(CHAR(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("account_out_id", "idempotency_key"),)

    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    BOX_RETENTION = "BOX_RETENTION"
    BOX_RELEASE = "BOX_RELEASE"
    BOX_WITHDRAWAL = "BOX_WITHDRAWAL"

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.account import Account
from models.base import Base


class Transaction(Base):
    """Uma operação financeira; os lançamentos dela moram em `ledger_entry`.

    `account_out_id` é a conta DONA da operação — é nela que a chave de
    idempotência vale, `UNIQUE(account_out_id, idempotency_key)`. Na
    transferência e no pagamento é a origem; no depósito, a conta que
    recebe; na tarifa, quem paga; nas operações da caixinha (`BOX_*`), a
    dona da caixinha. `account_in_id` só existe na transferência, quando
    há uma segunda conta do banco envolvida.

    Para que lado o dinheiro andou não se lê daqui: lê-se do `direction`
    de cada `ledger_entry`.
    """

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

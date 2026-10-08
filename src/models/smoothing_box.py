from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.account import Account
from models.base import Base


class SmoothingBox(Base):
    """A Caixinha de Equilíbrio: no máximo uma por conta, com saldo próprio."""

    __tablename__ = "smoothing_box"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    box_key = Column(UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
    account_id = Column(UUID(as_uuid=True), ForeignKey(Account.id), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False, server_default=text("0"))
    retention_pct = Column(SmallInteger, nullable=False)
    status = Column(String(10), nullable=False, server_default=text("'ACTIVE'"))
    activated_on = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("box_key"),
        UniqueConstraint("account_id"),
    )

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"

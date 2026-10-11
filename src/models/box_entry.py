from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base
from models.smoothing_box import SmoothingBox
from models.transaction import Transaction


class BoxEntry(Base):
    __tablename__ = "box_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    box_id = Column(UUID(as_uuid=True), ForeignKey(SmoothingBox.id), nullable=False)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey(Transaction.id), nullable=False)
    direction = Column(String(10), nullable=False)
    origin = Column(String(15), nullable=False)
    value = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("transaction_id"),)

    RETENTION = "RETENTION"
    RELEASE = "RELEASE"
    WITHDRAWAL = "WITHDRAWAL"

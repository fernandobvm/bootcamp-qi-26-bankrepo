from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base
from models.smoothing_box import SmoothingBox
from models.transaction import Transaction


class DailyClosing(Base):
    __tablename__ = "daily_closing"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    closing_key = Column(UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
    box_id = Column(UUID(as_uuid=True), ForeignKey(SmoothingBox.id), nullable=False)
    reference_date = Column(Date, nullable=False)
    income = Column(Numeric(15, 2), nullable=False)
    baseline = Column(Numeric(15, 2), nullable=False)
    window_days = Column(SmallInteger, nullable=False)
    lower_bound = Column(Numeric(15, 2), nullable=False)
    upper_bound = Column(Numeric(15, 2), nullable=False)
    band = Column(String(10), nullable=False)
    amount_calculated = Column(Numeric(15, 2), nullable=False)
    amount_moved = Column(Numeric(15, 2), nullable=False)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey(Transaction.id), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("closing_key"),
        UniqueConstraint("box_id", "reference_date"),
    )

    WARMUP = "WARMUP"
    ABOVE = "ABOVE"
    NEUTRAL = "NEUTRAL"
    BELOW = "BELOW"
    PAUSED = "PAUSED"

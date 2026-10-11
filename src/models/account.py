from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base
from models.customer import Customer


class Account(Base):
    __tablename__ = "account"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey(Customer.id), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False, server_default=text("0"))
    status = Column(String(20), nullable=False, server_default=text("'ATIVA'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("customer_id"),)

    ATIVA = "ATIVA"
    SUSPENSA = "SUSPENSA"
    ENCERRADA = "ENCERRADA"

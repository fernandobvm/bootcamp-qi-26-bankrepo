from sqlalchemy import CHAR, Column, Date, DateTime, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Customer(Base):
    """Versão mínima do cliente, só o que a caixinha precisa para existir.

    Segue o diagrama do RFC. As rotas de cadastro são da solução
    principal, e quem as escrever completa esta classe.
    """

    __tablename__ = "customer"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    document_number = Column(CHAR(14), nullable=False)
    name = Column(String(255), nullable=False)
    nationality = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("document_number"),)

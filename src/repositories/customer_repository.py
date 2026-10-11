from datetime import date
from typing import Optional
from uuid import UUID

from database import Context
from models import Customer


class CustomerRepository:
    """Grava e busca clientes. A conta de cada um mora no AccountRepository."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_data: dict, birth_date: date) -> Customer:
        customer = Customer()
        customer.name = customer_data["name"]
        customer.nationality = customer_data["nationality"]
        customer.document_number = customer_data["document_number"]
        customer.email = customer_data["email"]
        customer.birth_date = birth_date

        self.session.add(customer)

        # Flush aqui de propósito: é neste INSERT que o UNIQUE(document_number)
        # estoura quando duas requisições cadastram o mesmo CPF ao mesmo
        # tempo — e o controller precisa do `id` para criar a conta.
        self.session.flush()

        return customer

    def get_by_id(self, customer_id: UUID) -> Optional[Customer]:
        return self.session.query(Customer).filter(Customer.id == customer_id).first()

    def get_by_document_number(self, document_number: str) -> Optional[Customer]:
        return self.session.query(Customer).filter(Customer.document_number == document_number).first()

    def get_by_email(self, email: str) -> Customer:
        return self.session.query(Customer).filter(Customer.email == email).first()
    
    def list_page(self, limit: int, offset: int, filters: dict) -> list:
        query = self.session.query(Customer)

        name = filters.get("name")
        if name is not None:
            query = query.filter(Customer.name.ilike(f"%{name}%"))

        email = filter.get("email")
        if email is not None:
            query = query.filter(Customer.email == email)

        document_number = filters.get("document_number")
        if document_number is not None:
            query = query.filter(Customer.document_number == document_number)

        birthdate_from = filters.get("birthdate_from")
        if birthdate_from is not None:
            query = query.filter(Customer.birthdate >= birthdate_from)

        birthdate_to = filters.get("birthdate_to")
        if birthdate_to is not None:
            query = query.filter(Customer.birthdate <= birthdate_to)

        query = query.order_by(Customer.created_at.desc(), Customer.id.desc())

        return query.limit(limit + 1).offset(offset).all()
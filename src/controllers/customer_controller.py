from datetime import date
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import CustomerDTO
from errors import DuplicatedCustomer, InvalidCustomerDocument, InvalidSchema, NotFoundCustomer
from models import Customer
from repositories import AccountRepository, CustomerRepository
from utils.document_number import is_valid_cpf


class CustomerController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def create(self, payload: dict) -> dict:
        document_number = payload["document_number"]

        if not is_valid_cpf(document_number):
            raise InvalidCustomerDocument(document_number)

        birth_date = self._parse_birth_date(payload["birth_date"])

        # A consulta responde o caso comum; o pedido simultâneo que passar
        # por ela esbarra no UNIQUE(document_number), no except abaixo.
        if self.customer_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedCustomer(document_number)

        try:
            customer = self.customer_repository.create(payload, birth_date)
        except IntegrityError:
            self.session.rollback()
            raise DuplicatedCustomer(document_number)

        account = self.account_repository.create(customer.id)

        customer_dto = CustomerDTO.obj_to_dict(customer, account)
        self.session.commit()

        return customer_dto

    def get(self, customer_id: str) -> dict:
        customer = self._get_customer(customer_id)
        account = self.account_repository.get_by_customer(customer.id)

        return CustomerDTO.obj_to_dict(customer, account)

    def _get_customer(self, customer_id: str) -> Customer:
        try:
            parsed_customer_id = UUID(customer_id)
        except ValueError:
            raise NotFoundCustomer(customer_id)

        customer = self.customer_repository.get_by_id(parsed_customer_id)

        if customer is None:
            raise NotFoundCustomer(customer_id)

        return customer

    def _parse_birth_date(self, raw_birth_date: str) -> date:
        try:
            birth_date = date.fromisoformat(raw_birth_date)
        except ValueError:
            raise InvalidSchema(f"birth_date ({raw_birth_date}) is not a real date")

        if birth_date > self.account_repository.get_today():
            raise InvalidSchema(f"birth_date ({raw_birth_date}) is in the future")

        return birth_date

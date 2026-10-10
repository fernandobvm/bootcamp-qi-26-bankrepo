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
    """Cadastro de cliente: o cliente e a conta dele nascem no mesmo commit.

    Não existe cliente sem conta, nem conta sem cliente. Por isso os dois
    INSERTs moram na mesma transação de banco: se a conta falhar, o
    cliente também não fica.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def create(self, payload: dict) -> dict:
        """Os passos seguem o fluxo "Cadastro de cliente e conta" do RFC.

        A consulta pelo CPF antes do INSERT responde o caso comum com uma
        mensagem clara. Quem garante de verdade é o UNIQUE(document_number):
        duas requisições simultâneas com o mesmo CPF passam as duas pela
        consulta, e a segunda esbarra no índice — o `except` abaixo é o
        caminho dela.
        """
        document_number = payload["document_number"]

        if not is_valid_cpf(document_number):
            raise InvalidCustomerDocument(document_number)

        birth_date = self._parse_birth_date(payload["birth_date"])

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
        """O schema cobrou AAAA-MM-DD; aqui o calendário e o relógio.

        "2026-02-30" tem o formato certo e não existe, e uma data de
        nascimento no futuro também não. As duas são pedido malformado,
        400, como qualquer outro campo fora do formato.
        """
        try:
            birth_date = date.fromisoformat(raw_birth_date)
        except ValueError:
            raise InvalidSchema(f"birth_date ({raw_birth_date}) is not a real date")

        if birth_date > self.account_repository.get_today():
            raise InvalidSchema(f"birth_date ({raw_birth_date}) is in the future")

        return birth_date

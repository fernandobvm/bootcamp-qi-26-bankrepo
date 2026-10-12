import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from controllers.base_controller import BaseController
from errors import AccountNotActive, InvalidSchema, NotFoundAccount
from models import Account
from repositories import AccountRepository, TransactionRepository


class AccountBaseController(BaseController):

    def __init__(self, class_name: str) -> None:
        super().__init__(class_name)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def _get_account(self, account_id: str, for_update: bool = False) -> Account:
        # Texto que nem é UUID é 404, não um 500 do PostgreSQL.
        try:
            parsed_account_id = UUID(account_id)
        except ValueError:
            raise NotFoundAccount(account_id)

        account = self.account_repository.get_by_id(parsed_account_id, for_update=for_update)

        if account is None:
            raise NotFoundAccount(account_id)

        return account

    def _check_account_active(self, account: Account) -> None:
        if account.status != Account.ATIVA:
            raise AccountNotActive(account.id, account.status)

    def _parse_date(self, field_name: str, raw_date: str, error_class=InvalidSchema) -> date:
        # O schema cobra o formato; o calendário recusa "2026-02-30".
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            raise error_class(f"{field_name} ({raw_date}) is not a real date")

    def _parse_money(self, field_name: str, raw_value: str) -> Decimal:
        # Texto vira Decimal sem passar por float; o pattern do schema aceita "0.00".
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            raise InvalidSchema(f"{field_name} ({raw_value}) is not a valid amount")

        if value <= 0:
            raise InvalidSchema(f"{field_name} must be greater than zero")

        return value.quantize(Decimal("0.01"))

    def _hash_request(self, normalized_request: dict) -> str:
        # Sobre o pedido normalizado ("50" e "50.00" são o mesmo); a operação entra no hash.
        serialized = json.dumps(normalized_request, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

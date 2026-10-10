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
    """O que todo controller que mexe numa conta faz igual.

    Conta, transações e caixinha passam pelas mesmas portas: achar a
    conta (ou responder 404), exigir que ela esteja ATIVA, ler dinheiro
    sem passar por `float` e calcular o `request_hash` da idempotência.
    Cada regra mora aqui uma vez só, e um 404 de conta sai igual em
    todas as rotas.
    """

    def __init__(self, class_name: str) -> None:
        super().__init__(class_name)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def _get_account(self, account_id: str, for_update: bool = False) -> Account:
        # Um identificador que nem é UUID não pode ser de conta nenhuma:
        # é 404, e não um 500 vindo do PostgreSQL reclamando do tipo.
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
        """Converte a data, ou recusa com 400.

        O schema já cobrou o formato AAAA-MM-DD; quem sabe que fevereiro
        não tem dia 30 é o calendário, e é aqui que "2026-02-30" para.
        """
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            raise error_class(f"{field_name} ({raw_date}) is not a real date")

    def _parse_money(self, field_name: str, raw_value: str) -> Decimal:
        """Texto vira `Decimal` direto — o valor nunca passa por `float`.

        O schema garante até duas casas decimais; aqui só falta recusar o
        zero, que um `pattern` não sabe distinguir de "0.00".
        """
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            raise InvalidSchema(f"{field_name} ({raw_value}) is not a valid amount")

        if value <= 0:
            raise InvalidSchema(f"{field_name} must be greater than zero")

        return value.quantize(Decimal("0.01"))

    def _hash_request(self, normalized_request: dict) -> str:
        """A impressão digital do pedido, para comparar reenvios da mesma chave.

        Calculada sobre o pedido JÁ normalizado — o valor com duas casas,
        o UUID em minúsculas —, para que "50" e "50.00" sejam o mesmo
        pedido. A operação entra no hash: a mesma chave usada num
        depósito e depois numa transferência é reuso, e dá 409.
        """
        serialized = json.dumps(normalized_request, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

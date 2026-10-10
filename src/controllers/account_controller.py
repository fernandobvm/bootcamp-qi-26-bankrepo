from decimal import Decimal

from controllers.account_base_controller import AccountBaseController
from dtos import AccountDTO, TransactionDTO
from errors import AccountHasBalance, AccountStatusTransitionNotAllowed, InvalidParameter
from models import Account
from repositories import SmoothingBoxRepository

# O ciclo de vida da conta: de onde se pode ir para onde. ENCERRADA não
# tem saída — uma conta encerrada não volta, abre-se outra.
ALLOWED_TRANSITIONS = {
    Account.ATIVA: [Account.SUSPENSA, Account.ENCERRADA],
    Account.SUSPENSA: [Account.ATIVA, Account.ENCERRADA],
    Account.ENCERRADA: [],
}


class AccountController(AccountBaseController):
    """Saldo, ciclo de vida e extrato de uma conta."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.smoothing_box_repository = SmoothingBoxRepository(self.context)

    def get(self, account_id: str) -> dict:
        # Leitura sem trava: devolve o último saldo confirmado. Uma
        # transferência em andamento não aparece pela metade.
        account = self._get_account(account_id)

        return AccountDTO.obj_to_dict(account)

    def update_status(self, account_id: str, payload: dict) -> dict:
        """Muda o status, respeitando ALLOWED_TRANSITIONS.

        Encerrar exige saldo zero na conta e na caixinha: uma conta
        ENCERRADA não movimenta mais nada, e o dinheiro que estivesse
        dentro ficaria preso. A trava segue a ordem de sempre — conta,
        depois caixinha —, então nenhum fechamento ou resgate muda os
        saldos entre a conferência e o `commit`.
        """
        new_status = payload["status"]

        account = self._get_account(account_id, for_update=True)

        if new_status not in ALLOWED_TRANSITIONS[account.status]:
            raise AccountStatusTransitionNotAllowed(account.status, new_status)

        if new_status == Account.ENCERRADA:
            box_balance = Decimal("0.00")
            box = self.smoothing_box_repository.get_by_account(account.id, for_update=True)
            if box is not None:
                box_balance = box.balance

            if account.balance > 0 or box_balance > 0:
                raise AccountHasBalance(account.balance, box_balance)

        self.account_repository.update_status(account, new_status)

        self.session.flush()
        account_dto = AccountDTO.obj_to_dict(account)
        self.session.commit()

        return account_dto

    def list_statement(self, account_id: str, limit: int, offset: int, filters: dict) -> dict:
        """O extrato, na ordem do fluxo do RFC: datas, conta, status, lançamentos."""
        start_date = None
        if filters.get("start_date") is not None:
            start_date = self._parse_date("start_date", filters["start_date"], InvalidParameter)

        end_date = None
        if filters.get("end_date") is not None:
            end_date = self._parse_date("end_date", filters["end_date"], InvalidParameter)

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidParameter(f"start_date ({start_date}) is after end_date ({end_date})")

        account = self._get_account(account_id)
        self._check_account_active(account)

        rows = self.transaction_repository.list_statement(account.id, limit, offset, start_date, end_date)

        is_last_page = True
        if len(rows) > limit:
            is_last_page = False
            rows = rows[:-1]

        return {
            "statement_list_dto": TransactionDTO.statement_to_list_dict(rows),
            "is_last_page": is_last_page,
        }

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from constants import BANK_TIMEZONE
from database import Context
from models import Account


class AccountRepository:
    """Busca e trava contas. Versão mínima, do tamanho que a caixinha precisa."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_id(self, account_id: UUID, for_update: bool = False) -> Optional[Account]:
        """A conta, opcionalmente travada até o fim da transação.

        Com `for_update`, vira um `SELECT … FOR UPDATE`: outra requisição
        que peça a mesma linha espera o `commit` ou o `rollback` desta.
        É essa espera que impede duas operações de lerem o mesmo saldo e
        as duas acharem que ele cobre o valor.
        """
        query = self.session.query(Account).filter(Account.id == account_id)

        if for_update:
            query = query.with_for_update()

        return query.first()

    def debit(self, account: Account, value) -> None:
        account.balance = account.balance - value
        account.updated_at = func.now()

    def credit(self, account: Account, value) -> None:
        account.balance = account.balance + value
        account.updated_at = func.now()

    def get_today(self) -> date:
        """O dia de hoje no fuso do banco, perguntado ao PostgreSQL.

        O relógio que vale é o do banco de dados, não o do container da
        API: se os dois divergirem, quem grava o `created_at` dos
        lançamentos é o banco, e o "hoje" precisa concordar com ele.
        """
        return self.session.execute(select(cast(func.timezone(BANK_TIMEZONE, func.now()), Date))).scalar_one()

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from constants import BANK_TIMEZONE
from database import Context
from models import Account


class AccountRepository:
    """Cria, busca, trava e movimenta contas."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_id: UUID) -> Account:
        account = Account()
        account.customer_id = customer_id
        account.balance = Decimal("0.00")
        account.status = Account.ATIVA

        self.session.add(account)
        self.session.flush()

        return account

    def get_by_customer(self, customer_id: UUID) -> Optional[Account]:
        return self.session.query(Account).filter(Account.customer_id == customer_id).first()

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

    def lock_many(self, account_ids: List[UUID]) -> Dict[UUID, Account]:
        """Trava várias contas de uma vez, SEMPRE em ordem de `id`.

        É a regra que impede o deadlock da transferência: se A transfere
        para B enquanto B transfere para A, as duas requisições pedem as
        travas na mesma ordem (a do menor `id` primeiro), e a segunda
        simplesmente espera a primeira. Sem o `ORDER BY`, cada uma poderia
        travar a "sua" conta e ficar esperando a da outra para sempre.

        Conta que não existe simplesmente não vem no dicionário: quem
        chamou decide se isso é 404 de origem ou de destino.
        """
        accounts = (
            self.session.query(Account)
            .filter(Account.id.in_(account_ids))
            .order_by(Account.id)
            .with_for_update()
            .all()
        )

        accounts_by_id = {}
        for account in accounts:
            accounts_by_id[account.id] = account

        return accounts_by_id

    def update_status(self, account: Account, status: str) -> None:
        account.status = status
        account.updated_at = func.now()

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

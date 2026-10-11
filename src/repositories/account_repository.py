from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from constants import BANK_TIMEZONE
from database import Context
from models import Account


class AccountRepository:
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
        query = self.session.query(Account).filter(Account.id == account_id)

        if for_update:
            query = query.with_for_update()

        return query.first()

    def lock_many(self, account_ids: List[UUID]) -> Dict[UUID, Account]:
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
        return self.session.execute(select(cast(func.timezone(BANK_TIMEZONE, func.now()), Date))).scalar_one()

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import DateTime, func, literal

from constants import BANK_TIMEZONE
from database import Context
from models import LedgerEntry, Transaction


class TransactionRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_idempotency_key(self, account_id: UUID, idempotency_key: str) -> Optional[Transaction]:
        return (
            self.session.query(Transaction)
            .filter(
                Transaction.account_out_id == account_id,
                Transaction.idempotency_key == idempotency_key,
            )
            .first()
        )

    def create(
        self,
        transaction_type: str,
        account_out_id: UUID,
        value: Decimal,
        idempotency_key: str,
        request_hash: str,
        account_in_id: Optional[UUID] = None,
        related_transaction_id: Optional[UUID] = None,
    ) -> Transaction:
        transaction = Transaction()
        transaction.type = transaction_type
        transaction.account_out_id = account_out_id
        transaction.account_in_id = account_in_id
        transaction.value = value
        transaction.idempotency_key = idempotency_key
        transaction.request_hash = request_hash
        transaction.related_transaction_id = related_transaction_id

        self.session.add(transaction)
        self.session.flush()

        return transaction

    def add_ledger_entry(
        self, transaction: Transaction, account_id: UUID, direction: str, value: Decimal, balance_after: Decimal
    ) -> LedgerEntry:
        ledger_entry = LedgerEntry()
        ledger_entry.transaction_id = transaction.id
        ledger_entry.account_id = account_id
        ledger_entry.direction = direction
        ledger_entry.value = value
        ledger_entry.balance_after = balance_after

        self.session.add(ledger_entry)
        return ledger_entry

    def get_ledger_entry(self, transaction_id: UUID, account_id: UUID) -> Optional[LedgerEntry]:
        return (
            self.session.query(LedgerEntry)
            .filter(LedgerEntry.transaction_id == transaction_id, LedgerEntry.account_id == account_id)
            .first()
        )

    def get_related(self, transaction_id: UUID) -> Optional[Transaction]:
        return self.session.query(Transaction).filter(Transaction.related_transaction_id == transaction_id).first()

    def list_statement(
        self,
        account_id: UUID,
        limit: int,
        offset: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Tuple[LedgerEntry, Transaction]]:
        query = (
            self.session.query(LedgerEntry, Transaction)
            .join(Transaction, Transaction.id == LedgerEntry.transaction_id)
            .filter(LedgerEntry.account_id == account_id)
        )

        if start_date is not None:
            period_start = datetime.combine(start_date, time.min)
            query = query.filter(LedgerEntry.created_at >= func.timezone(BANK_TIMEZONE, literal(period_start, DateTime())))

        if end_date is not None:
            period_end = datetime.combine(end_date + timedelta(days=1), time.min)
            query = query.filter(LedgerEntry.created_at < func.timezone(BANK_TIMEZONE, literal(period_end, DateTime())))

        query = query.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())

        # Um a mais que o limite, só pra saber se existe próxima página.
        return query.limit(limit + 1).offset(offset).all()

    def count_transfers_since(self, account_id: UUID, first_day: date) -> int:
        period_start = datetime.combine(first_day, time.min)

        return (
            self.session.query(func.count(Transaction.id))
            .filter(
                Transaction.account_out_id == account_id,
                Transaction.type == Transaction.TRANSFER,
                Transaction.created_at >= func.timezone(BANK_TIMEZONE, literal(period_start, DateTime())),
            )
            .scalar()
        )

    def sum_income_of_day(self, account_id: UUID, day: date, excluded_types: list) -> Decimal:
        day_start = datetime.combine(day, time.min)
        next_day_start = datetime.combine(day + timedelta(days=1), time.min)

        total = (
            self.session.query(func.coalesce(func.sum(LedgerEntry.value), 0))
            .join(Transaction, Transaction.id == LedgerEntry.transaction_id)
            .filter(
                LedgerEntry.account_id == account_id,
                LedgerEntry.direction == LedgerEntry.CREDITO,
                Transaction.type.notin_(excluded_types),
                LedgerEntry.created_at >= func.timezone(BANK_TIMEZONE, literal(day_start, DateTime())),
                LedgerEntry.created_at < func.timezone(BANK_TIMEZONE, literal(next_day_start, DateTime())),
            )
            .scalar()
        )

        return Decimal(total)

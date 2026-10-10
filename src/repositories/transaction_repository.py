from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, func, literal

from constants import BANK_TIMEZONE
from database import Context
from models import LedgerEntry, Transaction


class TransactionRepository:
    """Grava operações e lançamentos, e responde perguntas sobre eles."""

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
    ) -> Transaction:
        transaction = Transaction()
        transaction.type = transaction_type
        transaction.account_out_id = account_out_id
        transaction.account_in_id = account_in_id
        transaction.value = value
        transaction.idempotency_key = idempotency_key
        transaction.request_hash = request_hash

        self.session.add(transaction)

        # O flush manda o INSERT agora, ainda dentro da transação: o
        # banco devolve o `id`, que os lançamentos logo abaixo precisam.
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

    def sum_income_of_day(self, account_id: UUID, day: date, excluded_types: list) -> Decimal:
        """A renda de um dia: os créditos da conta entre 00:00 e 24:00 de São Paulo.

        Duas escolhas aqui decidem o número, e as duas estão no RFC:

        • Só entra CREDITO, e não de qualquer tipo: o que a própria
          caixinha devolveu (`BOX_RELEASE`) ou o que o cliente resgatou
          (`BOX_WITHDRAWAL`) não é renda. Se entrasse, cada liberação
          inflaria a média do dia seguinte.
        • O dia é o do fuso do banco. O `timezone(...)` converte "meia-
          noite em São Paulo" para um instante absoluto, e a comparação
          com o `created_at` (que é TIMESTAMPTZ) usa o índice
          `ledger_entry_account_created_at` sem converter linha por linha.
        """
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

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from dtos.formatters import bank_datetime, money
from models import LedgerEntry, Transaction


def optional_id(value: Optional[UUID]) -> Optional[str]:
    if value is None:
        return None

    return str(value)


class TransactionDTO:
    @staticmethod
    def deposit_to_dict(transaction: Transaction, ledger_entry: LedgerEntry) -> dict:
        return {
            "transaction_id": str(transaction.id),
            "type": transaction.type,
            "account_id": str(transaction.account_out_id),
            "value": money(transaction.value),
            "balance_after": money(ledger_entry.balance_after),
            "created_at": bank_datetime(transaction.created_at),
        }

    @staticmethod
    def transfer_to_dict(transfer: Transaction, fee: Optional[Transaction], last_debit: LedgerEntry) -> dict:
        fee_value = Decimal("0.00")
        fee_transaction_id = None
        if fee is not None:
            fee_value = fee.value
            fee_transaction_id = fee.id

        return {
            "transaction_id": str(transfer.id),
            "type": transfer.type,
            "account_id_out": str(transfer.account_out_id),
            "account_id_in": str(transfer.account_in_id),
            "value": money(transfer.value),
            "fee": money(fee_value),
            "fee_transaction_id": optional_id(fee_transaction_id),
            "total_debited": money(transfer.value + fee_value),
            "balance_after": money(last_debit.balance_after),
            "created_at": bank_datetime(transfer.created_at),
        }

    @staticmethod
    def payment_to_dict(transaction: Transaction, ledger_entry: LedgerEntry) -> dict:
        return {
            "transaction_id": str(transaction.id),
            "type": transaction.type,
            "account_id_out": str(transaction.account_out_id),
            "value": money(transaction.value),
            "balance_after": money(ledger_entry.balance_after),
            "created_at": bank_datetime(transaction.created_at),
        }

    @staticmethod
    def statement_entry_to_dict(ledger_entry: LedgerEntry, transaction: Transaction) -> dict:
        counterparty_account_id = None
        if transaction.type == Transaction.TRANSFER:
            if ledger_entry.direction == LedgerEntry.DEBITO:
                counterparty_account_id = transaction.account_in_id
            else:
                counterparty_account_id = transaction.account_out_id

        return {
            "transaction_id": str(transaction.id),
            "type": transaction.type,
            "direction": ledger_entry.direction,
            "value": money(ledger_entry.value),
            "balance_after": money(ledger_entry.balance_after),
            "counterparty_account_id": optional_id(counterparty_account_id),
            "related_transaction_id": optional_id(transaction.related_transaction_id),
            "created_at": bank_datetime(ledger_entry.created_at),
        }

    @staticmethod
    def statement_to_list_dict(rows: List[tuple]) -> List[dict]:
        statement = []

        for ledger_entry, transaction in rows:
            statement.append(TransactionDTO.statement_entry_to_dict(ledger_entry, transaction))

        return statement

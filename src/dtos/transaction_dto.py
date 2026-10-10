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
    """Depósito, transferência, pagamento e extrato no JSON da resposta.

    Toda resposta de operação é montada SÓ com o que ficou gravado: o
    saldo vem do `balance_after` do lançamento, e não do saldo de agora.
    É isso que deixa um reenvio da mesma chave, dias depois, receber
    exatamente o corpo da primeira resposta.
    """

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
        """A transferência e a tarifa dela, numa resposta só.

        Transferência isenta tem `fee` "0.00" e `fee_transaction_id`
        nulo. O `balance_after` é o da origem depois de TUDO — o último
        débito, que é o da tarifa quando ela existe.
        """
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
        """Uma linha do extrato, do ponto de vista da conta consultada.

        A contraparte só existe na transferência: para quem mandou é a
        conta de destino, para quem recebeu é a de origem. Depósito,
        tarifa e pagamento têm o outro lado fora do banco.
        """
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

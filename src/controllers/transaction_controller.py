from uuid import UUID

from controllers.account_base_controller import AccountBaseController
from controllers.transfer_fee_rule import calculate_transfer_fee
from dtos import TransactionDTO
from errors import (
    IdempotencyKeyReused,
    InsufficientBalance,
    NotFoundAccount,
    NotFoundDestinationAccount,
    SameAccountTransfer,
)
from models import Account, LedgerEntry, Transaction


class TransactionController(AccountBaseController):
    """Depósito, transferência e pagamento: as operações que movem saldo."""

    def __init__(self) -> None:
        super().__init__(__name__)

    def deposit(self, account_id: str, payload: dict) -> dict:
        """Dinheiro que chega de fora do banco: um crédito, sem contraparte aqui."""
        value = self._parse_money("value", payload["value"])
        idempotency_key = payload["idempotency_key"]
        request_hash = self._hash_request({"operation": Transaction.DEPOSIT, "value": f"{value:.2f}"})

        account = self._get_account(account_id, for_update=True)

        previous = self._find_previous(account, idempotency_key, request_hash)
        if previous is not None:
            ledger_entry = self.transaction_repository.get_ledger_entry(previous.id, account.id)
            return TransactionDTO.deposit_to_dict(previous, ledger_entry)

        self._check_account_active(account)

        transaction = self.transaction_repository.create(
            transaction_type=Transaction.DEPOSIT,
            account_out_id=account.id,
            value=value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self.account_repository.credit(account, value)
        ledger_entry = self.transaction_repository.add_ledger_entry(
            transaction, account.id, LedgerEntry.CREDITO, value, account.balance
        )

        self.session.flush()
        deposit_dto = TransactionDTO.deposit_to_dict(transaction, ledger_entry)
        self.session.commit()

        return deposit_dto

    def transfer(self, account_id_out: str, payload: dict) -> dict:
        """Debita a origem, credita o destino e cobra a tarifa no mesmo commit."""
        value = self._parse_money("value", payload["value"])
        idempotency_key = payload["idempotency_key"]

        out_id = self._parse_account_id(account_id_out, NotFoundAccount)
        in_id = self._parse_account_id(payload["account_id_in"], NotFoundDestinationAccount)

        if out_id == in_id:
            raise SameAccountTransfer(out_id)

        request_hash = self._hash_request(
            {"operation": Transaction.TRANSFER, "account_id_in": str(in_id), "value": f"{value:.2f}"}
        )

        # Travadas em ordem de id: transferências opostas não formam deadlock.
        accounts = self.account_repository.lock_many([out_id, in_id])

        account_out = accounts.get(out_id)
        if account_out is None:
            raise NotFoundAccount(out_id)

        previous = self._find_previous(account_out, idempotency_key, request_hash)
        if previous is not None:
            return self._rebuild_transfer(previous)

        account_in = accounts.get(in_id)
        if account_in is None:
            raise NotFoundDestinationAccount(in_id)

        self._check_account_active(account_out)
        self._check_account_active(account_in)

        # Contada com a origem travada: a última isenção do mês vai para um pedido só.
        first_day_of_month = self.account_repository.get_today().replace(day=1)
        transfers_this_month = self.transaction_repository.count_transfers_since(account_out.id, first_day_of_month)
        fee_value = calculate_transfer_fee(value, transfers_this_month)

        total = value + fee_value
        if account_out.balance < total:
            raise InsufficientBalance(total, account_out.balance)

        transfer = self.transaction_repository.create(
            transaction_type=Transaction.TRANSFER,
            account_out_id=account_out.id,
            account_in_id=account_in.id,
            value=value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self.account_repository.debit(account_out, value)
        last_debit = self.transaction_repository.add_ledger_entry(
            transfer, account_out.id, LedgerEntry.DEBITO, value, account_out.balance
        )
        self.account_repository.credit(account_in, value)
        self.transaction_repository.add_ledger_entry(
            transfer, account_in.id, LedgerEntry.CREDITO, value, account_in.balance
        )

        # Isenta não grava FEE: R$ 0,00 nem passaria no CHECK (value > 0).
        fee = None
        if fee_value > 0:
            # Chave derivada da transferência: uma segunda tarifa esbarraria no UNIQUE.
            fee_key = f"fee:{transfer.id}"
            fee = self.transaction_repository.create(
                transaction_type=Transaction.FEE,
                account_out_id=account_out.id,
                value=fee_value,
                idempotency_key=fee_key,
                request_hash=self._hash_request({"operation": Transaction.FEE, "key": fee_key}),
                related_transaction_id=transfer.id,
            )
            self.account_repository.debit(account_out, fee_value)
            last_debit = self.transaction_repository.add_ledger_entry(
                fee, account_out.id, LedgerEntry.DEBITO, fee_value, account_out.balance
            )

        self.session.flush()
        transfer_dto = TransactionDTO.transfer_to_dict(transfer, fee, last_debit)
        self.session.commit()

        return transfer_dto

    def payment(self, account_id_out: str, payload: dict) -> dict:
        """Como a transferência, com uma conta só e sem tarifa."""
        value = self._parse_money("value", payload["value"])
        idempotency_key = payload["idempotency_key"]
        request_hash = self._hash_request({"operation": Transaction.PAYMENT, "value": f"{value:.2f}"})

        account = self._get_account(account_id_out, for_update=True)

        previous = self._find_previous(account, idempotency_key, request_hash)
        if previous is not None:
            ledger_entry = self.transaction_repository.get_ledger_entry(previous.id, account.id)
            return TransactionDTO.payment_to_dict(previous, ledger_entry)

        self._check_account_active(account)

        if account.balance < value:
            raise InsufficientBalance(value, account.balance)

        transaction = self.transaction_repository.create(
            transaction_type=Transaction.PAYMENT,
            account_out_id=account.id,
            value=value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self.account_repository.debit(account, value)
        ledger_entry = self.transaction_repository.add_ledger_entry(
            transaction, account.id, LedgerEntry.DEBITO, value, account.balance
        )

        self.session.flush()
        payment_dto = TransactionDTO.payment_to_dict(transaction, ledger_entry)
        self.session.commit()

        return payment_dto

    def _find_previous(self, account: Account, idempotency_key: str, request_hash: str):
        # Chamado com a conta já travada: reenvios simultâneos da mesma chave
        # fazem fila, e o segundo enxerga a transação do primeiro.
        previous = self.transaction_repository.get_by_idempotency_key(account.id, idempotency_key)

        if previous is None:
            return None

        if previous.request_hash != request_hash:
            raise IdempotencyKeyReused(idempotency_key)

        return previous

    def _rebuild_transfer(self, transfer: Transaction) -> dict:
        # O último débito na origem é o da tarifa, quando houve tarifa.
        fee = self.transaction_repository.get_related(transfer.id)

        if fee is not None:
            last_debit = self.transaction_repository.get_ledger_entry(fee.id, transfer.account_out_id)
        else:
            last_debit = self.transaction_repository.get_ledger_entry(transfer.id, transfer.account_out_id)

        return TransactionDTO.transfer_to_dict(transfer, fee, last_debit)

    def _parse_account_id(self, raw_account_id: str, not_found_error) -> UUID:
        # Texto que nem é UUID não é conta nenhuma: 404 da ponta a que se refere.
        try:
            return UUID(raw_account_id)
        except ValueError:
            raise not_found_error(raw_account_id)

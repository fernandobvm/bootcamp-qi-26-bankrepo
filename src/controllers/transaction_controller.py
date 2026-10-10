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
    """Depósito, transferência e pagamento: as operações que movem saldo.

    ────────────────────────────────────────────────────────────────
    O DESENHO QUE AS TRÊS REPETEM
    ────────────────────────────────────────────────────────────────
    1. Lê o valor como `Decimal` e calcula o `request_hash` do pedido.
    2. Trava as contas envolvidas com `SELECT … FOR UPDATE`.
    3. Procura a `idempotency_key` na conta dona da operação. Achou com
       o mesmo hash: devolve a resposta da primeira vez, montada do que
       ficou gravado, sem mover nada. Achou com outro hash: 409.
    4. Confere status e saldo — com as linhas travadas, nenhum outro
       pedido muda esses números até o `commit`.
    5. Grava a `transaction`, os `ledger_entry` e os saldos novos, e o
       `commit` é a última linha antes do `return`: ou tudo fica, ou
       nada fica.

    A procura pela chave vem DEPOIS da trava de propósito. Dois reenvios
    simultâneos da mesma chave fazem fila na trava; o segundo, quando
    passa, já enxerga a transação do primeiro e devolve o corpo dela.
    """

    def __init__(self) -> None:
        super().__init__(__name__)

    # ────────────────────────────────────────────────────────────────
    # Depósito
    # ────────────────────────────────────────────────────────────────

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

    # ────────────────────────────────────────────────────────────────
    # Transferência
    # ────────────────────────────────────────────────────────────────

    def transfer(self, account_id_out: str, payload: dict) -> dict:
        """Debita a origem, credita o destino e cobra a tarifa — três escritas, um commit.

        A tarifa segue o transfer_fee_rule: as primeiras do mês são
        isentas, depois é um percentual com mínimo. Quando há tarifa, ela
        é uma `transaction` própria, do tipo FEE, ligada à transferência
        por `related_transaction_id`. Assim o extrato mostra as duas
        linhas separadas ("transferi 500", "paguei 5 de tarifa"), e a
        transferência continua dizendo só quanto andou de uma conta para
        a outra. O saldo da origem precisa cobrir valor + tarifa: não
        existe transferência que passa e tarifa que fica devendo.
        """
        value = self._parse_money("value", payload["value"])
        idempotency_key = payload["idempotency_key"]

        out_id = self._parse_account_id(account_id_out, NotFoundAccount)
        in_id = self._parse_account_id(payload["account_id_in"], NotFoundDestinationAccount)

        if out_id == in_id:
            raise SameAccountTransfer(out_id)

        request_hash = self._hash_request(
            {"operation": Transaction.TRANSFER, "account_id_in": str(in_id), "value": f"{value:.2f}"}
        )

        # As duas contas numa consulta só, travadas em ordem de id — o
        # porquê está no AccountRepository.lock_many.
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

        # A contagem do mês acontece com a origem já travada: duas
        # transferências simultâneas da mesma conta fazem fila, e a
        # segunda enxerga a primeira — nunca as duas pegam a última vaga
        # da franquia.
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

        # Transferência isenta não grava tarifa nenhuma: uma FEE de R$ 0,00
        # nem passaria no CHECK (value > 0), e o extrato não ganha uma
        # linha que não move dinheiro.
        fee = None
        if fee_value > 0:
            # A chave da tarifa é DETERMINÍSTICA, derivada da transferência:
            # uma segunda tarifa para a mesma transferência esbarraria no
            # UNIQUE(account_out_id, idempotency_key) e no
            # UNIQUE(related_transaction_id).
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

    # ────────────────────────────────────────────────────────────────
    # Pagamento
    # ────────────────────────────────────────────────────────────────

    def payment(self, account_id_out: str, payload: dict) -> dict:
        """O mesmo desenho da transferência, com uma conta só e sem tarifa.

        O destino está fora do banco, então só existe o débito. A tarifa é
        da transferência (A1 p.4), e o pagamento não paga nenhuma.
        """
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

    # ────────────────────────────────────────────────────────────────
    # Peças internas
    # ────────────────────────────────────────────────────────────────

    def _find_previous(self, account: Account, idempotency_key: str, request_hash: str):
        """A transação de um pedido anterior com a mesma chave, se houver.

        Mesma chave e mesmo hash: é um reenvio, e quem chamou devolve a
        resposta original. Mesma chave e outro hash: 409. Chave nova:
        None, e a operação segue.
        """
        previous = self.transaction_repository.get_by_idempotency_key(account.id, idempotency_key)

        if previous is None:
            return None

        if previous.request_hash != request_hash:
            raise IdempotencyKeyReused(idempotency_key)

        return previous

    def _rebuild_transfer(self, transfer: Transaction) -> dict:
        """A resposta original, montada do que ficou gravado.

        O último débito na origem é o da tarifa, se houve tarifa; se a
        transferência foi isenta, é o da própria transferência.
        """
        fee = self.transaction_repository.get_related(transfer.id)

        if fee is not None:
            last_debit = self.transaction_repository.get_ledger_entry(fee.id, transfer.account_out_id)
        else:
            last_debit = self.transaction_repository.get_ledger_entry(transfer.id, transfer.account_out_id)

        return TransactionDTO.transfer_to_dict(transfer, fee, last_debit)

    def _parse_account_id(self, raw_account_id: str, not_found_error) -> UUID:
        # O mesmo cuidado do _get_account: um texto que nem é UUID não é
        # conta nenhuma, e responde o 404 da ponta a que ele se refere.
        try:
            return UUID(raw_account_id)
        except ValueError:
            raise not_found_error(raw_account_id)

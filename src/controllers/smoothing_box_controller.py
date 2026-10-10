from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from controllers.account_base_controller import AccountBaseController
from controllers.smoothing_box_rule import WINDOW_DAYS, calculate_closing
from dtos import SmoothingBoxDTO
from errors import (
    DuplicatedSmoothingBox,
    IdempotencyKeyReused,
    InsufficientBoxBalance,
    InvalidParameter,
    InvalidReferenceDate,
    NotFoundSmoothingBox,
    PreviousDayNotClosed,
    SmoothingBoxSameStatus,
)
from models import Account, BoxEntry, DailyClosing, LedgerEntry, SmoothingBox, Transaction
from repositories import SmoothingBoxRepository

DEFAULT_RETENTION_PCT = 50

# A renda do dia não conta o que veio da própria caixinha.
NOT_INCOME_TYPES = [Transaction.BOX_RELEASE, Transaction.BOX_WITHDRAWAL]


class SmoothingBoxController(AccountBaseController):
    """As regras da Caixinha de Equilíbrio: ativar, fechar o dia e resgatar.

    ────────────────────────────────────────────────────────────────
    A ORDEM DAS TRAVAS — CONTA, DEPOIS CAIXINHA, SEMPRE
    ────────────────────────────────────────────────────────────────
    Fechamento e resgate mexem em dois saldos, e os dois travam as duas
    linhas na MESMA ordem: primeiro a conta, depois a caixinha. Com a
    ordem fixa, duas requisições nunca ficam cada uma segurando a linha
    que a outra espera (o deadlock). A transferência do time trava só a
    conta, então ela espera o fechamento terminar e segue.

    E o `commit` é sempre a última linha antes do `return`: as travas só
    saem quando tudo — os dois saldos, os lançamentos e o fechamento —
    já está gravado junto.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.smoothing_box_repository = SmoothingBoxRepository(self.context)

    # ────────────────────────────────────────────────────────────────
    # Ativar, consultar, alterar
    # ────────────────────────────────────────────────────────────────

    def create(self, account_id: str, payload: dict) -> dict:
        retention_pct = payload.get("retention_pct", DEFAULT_RETENTION_PCT)

        # A trava na conta serializa duas ativações simultâneas: a segunda
        # espera, encontra a caixinha da primeira e recebe 409. O UNIQUE
        # (account_id) logo abaixo é a rede de segurança se algo escapar.
        account = self._get_account(account_id, for_update=True)
        self._check_account_active(account)

        if self.smoothing_box_repository.get_by_account(account.id) is not None:
            raise DuplicatedSmoothingBox(account.id)

        today = self.account_repository.get_today()

        try:
            box = self.smoothing_box_repository.create(account.id, int(retention_pct), today)
        except IntegrityError:
            self.session.rollback()
            raise DuplicatedSmoothingBox(account.id)

        box_dto = self._box_to_dict(box)
        self.session.commit()

        return box_dto

    def get(self, account_id: str) -> dict:
        account = self._get_account(account_id)
        box = self._get_box(account)

        return self._box_to_dict(box)

    def update(self, account_id: str, payload: dict) -> dict:
        account = self._get_account(account_id, for_update=True)
        box = self._get_box(account, for_update=True)

        new_status = payload.get("status")
        if new_status is not None and new_status == box.status:
            raise SmoothingBoxSameStatus(box.status)

        self.smoothing_box_repository.update(box, payload.get("retention_pct"), new_status)

        self.session.flush()
        box_dto = self._box_to_dict(box)
        self.session.commit()

        return box_dto

    # ────────────────────────────────────────────────────────────────
    # Fechar o dia
    # ────────────────────────────────────────────────────────────────

    def close_day(self, account_id: str, raw_reference_date: str) -> Tuple[dict, bool]:
        """Fecha um dia. Devolve o fechamento e se ele é NOVO (201) ou já existia (200).

        Os passos seguem o fluxo "Fechar o dia — caminho feliz" do RFC, e
        a ordem é a garantia:

        1. Dia que ainda não acabou é recusado antes de qualquer trava.
        2. Trava a conta e a caixinha.
        3. O dia já está fechado? Devolve o fechamento existente e não
           move nada — é aqui que um reenvio, ou a segunda de duas
           requisições simultâneas, para.
        4. O dia anterior precisa estar fechado.
        5. Calcula e, se houver o que mover, move e grava tudo junto.
        """
        reference_date = self._parse_date("reference_date", raw_reference_date)

        today = self.account_repository.get_today()
        if reference_date >= today:
            raise InvalidReferenceDate(reference_date, "the day has not ended yet")

        account = self._get_account(account_id, for_update=True)
        box = self._get_box(account, for_update=True)
        self._check_account_active(account)

        if reference_date < box.activated_on:
            raise InvalidReferenceDate(reference_date, f"the smoothing box was activated on {box.activated_on}")

        existing_closing = self.smoothing_box_repository.get_closing(box.id, reference_date)
        if existing_closing is not None:
            return SmoothingBoxDTO.closing_to_dict(existing_closing), False

        if reference_date > box.activated_on:
            previous_day = reference_date - timedelta(days=1)

            if self.smoothing_box_repository.get_closing(box.id, previous_day) is None:
                raise PreviousDayNotClosed(reference_date, self._next_reference_date(box))

        window_incomes = self.smoothing_box_repository.get_window_incomes(box.id, reference_date, WINDOW_DAYS)
        income = self.transaction_repository.sum_income_of_day(account.id, reference_date, NOT_INCOME_TYPES)

        result = calculate_closing(
            window_incomes=window_incomes,
            income=income,
            box_status=box.status,
            retention_pct=box.retention_pct,
            box_balance=box.balance,
            account_balance=account.balance,
        )

        try:
            transaction_id = self._move_closing_amount(account, box, reference_date, result)
            closing = self.smoothing_box_repository.add_closing(box.id, reference_date, result, transaction_id)
        except IntegrityError:
            # Alguém fechou o mesmo dia por um caminho que escapou da
            # trava. O rollback desfaz TUDO o que esta requisição fez,
            # inclusive o movimento de dinheiro, e quem responde é o
            # fechamento que chegou primeiro.
            self.session.rollback()
            existing_closing = self._get_closing_after_conflict(account.id, reference_date)
            return SmoothingBoxDTO.closing_to_dict(existing_closing), False

        closing_dto = SmoothingBoxDTO.closing_to_dict(closing)
        self.session.commit()

        return closing_dto, True

    def list_closings(self, account_id: str, limit: int, offset: int, filters: dict) -> dict:
        account = self._get_account(account_id)
        box = self._get_box(account)

        start_date = None
        if filters.get("start_date") is not None:
            start_date = self._parse_date("start_date", filters["start_date"], InvalidParameter)

        end_date = None
        if filters.get("end_date") is not None:
            end_date = self._parse_date("end_date", filters["end_date"], InvalidParameter)

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidParameter(f"start_date ({start_date}) is after end_date ({end_date})")

        closings = self.smoothing_box_repository.list_closings(box.id, limit, offset, start_date, end_date)

        is_last_page = True
        if len(closings) > limit:
            is_last_page = False
            closings = closings[:-1]

        return {
            "closings_list_dto": SmoothingBoxDTO.list_closings_to_list_dict(closings),
            "is_last_page": is_last_page,
        }

    # ────────────────────────────────────────────────────────────────
    # Resgatar
    # ────────────────────────────────────────────────────────────────

    def withdraw(self, account_id: str, payload: dict) -> dict:
        """Tira dinheiro da caixinha e põe na conta. Idempotente pela chave.

        Um reenvio com a mesma chave e o mesmo valor devolve o corpo da
        primeira vez, montado a partir do que ficou gravado; com a mesma
        chave e outro valor, 409. A comparação é pelo `request_hash`,
        calculado sobre o valor JÁ normalizado: "50" e "50.00" são o
        mesmo pedido.
        """
        value = self._parse_money("value", payload["value"])
        idempotency_key = payload["idempotency_key"]
        request_hash = self._hash_request({"operation": Transaction.BOX_WITHDRAWAL, "value": f"{value:.2f}"})

        account = self._get_account(account_id, for_update=True)
        box = self._get_box(account, for_update=True)

        previous = self.transaction_repository.get_by_idempotency_key(account.id, idempotency_key)
        if previous is not None:
            if previous.request_hash != request_hash:
                raise IdempotencyKeyReused(idempotency_key)

            return self._rebuild_withdrawal(previous, account.id)

        self._check_account_active(account)

        if value > box.balance:
            raise InsufficientBoxBalance(f"{value:.2f}", box.balance)

        transaction = self.transaction_repository.create(
            transaction_type=Transaction.BOX_WITHDRAWAL,
            account_out_id=account.id,
            value=value,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        box_entry = self.smoothing_box_repository.add_entry(
            box, transaction.id, LedgerEntry.DEBITO, BoxEntry.WITHDRAWAL, value
        )
        self.account_repository.credit(account, value)
        ledger_entry = self.transaction_repository.add_ledger_entry(
            transaction, account.id, LedgerEntry.CREDITO, value, account.balance
        )

        self.session.flush()
        withdrawal_dto = SmoothingBoxDTO.withdrawal_to_dict(transaction, box_entry, ledger_entry)
        self.session.commit()

        return withdrawal_dto

    # ────────────────────────────────────────────────────────────────
    # Peças internas
    # ────────────────────────────────────────────────────────────────

    def _move_closing_amount(
        self, account: Account, box: SmoothingBox, reference_date: date, result: dict
    ) -> Optional[UUID]:
        """Move o valor do fechamento entre conta e caixinha, se houver valor.

        A chave de idempotência da transação é DETERMINÍSTICA —
        `closing:{box_id}:{data}` —, e não um número aleatório: dois
        fechamentos do mesmo dia gerariam a mesma chave e o segundo
        esbarraria no UNIQUE(account_out_id, idempotency_key). É uma
        segunda rede, além do UNIQUE do próprio fechamento.
        """
        amount = result["amount_moved"]

        if amount <= 0:
            return None

        idempotency_key = f"closing:{box.id}:{reference_date.isoformat()}"

        if result["band"] == DailyClosing.ABOVE:
            transaction_type = Transaction.BOX_RETENTION
            account_direction = LedgerEntry.DEBITO
            box_direction = LedgerEntry.CREDITO
            box_origin = BoxEntry.RETENTION
        else:
            transaction_type = Transaction.BOX_RELEASE
            account_direction = LedgerEntry.CREDITO
            box_direction = LedgerEntry.DEBITO
            box_origin = BoxEntry.RELEASE

        transaction = self.transaction_repository.create(
            transaction_type=transaction_type,
            account_out_id=account.id,
            value=amount,
            idempotency_key=idempotency_key,
            request_hash=self._hash_request({"operation": transaction_type, "key": idempotency_key}),
        )

        if account_direction == LedgerEntry.DEBITO:
            self.account_repository.debit(account, amount)
        else:
            self.account_repository.credit(account, amount)

        self.transaction_repository.add_ledger_entry(transaction, account.id, account_direction, amount, account.balance)
        self.smoothing_box_repository.add_entry(box, transaction.id, box_direction, box_origin, amount)

        return transaction.id

    def _get_closing_after_conflict(self, account_id: UUID, reference_date: date) -> DailyClosing:
        box = self.smoothing_box_repository.get_by_account(account_id)
        closing = self.smoothing_box_repository.get_closing(box.id, reference_date)

        if closing is None:
            raise Exception(f"Conflito ao fechar {reference_date}, mas nenhum fechamento foi encontrado depois dele.")

        return closing

    def _rebuild_withdrawal(self, transaction: Transaction, account_id: UUID) -> dict:
        box_entry = self.smoothing_box_repository.get_entry_by_transaction(transaction.id)
        ledger_entry = self.transaction_repository.get_ledger_entry(transaction.id, account_id)

        return SmoothingBoxDTO.withdrawal_to_dict(transaction, box_entry, ledger_entry)

    def _box_to_dict(self, box: SmoothingBox) -> dict:
        """A caixinha, com a média e as faixas que valeriam no PRÓXIMO fechamento."""
        window_incomes = self.smoothing_box_repository.get_window_incomes(box.id, None, WINDOW_DAYS)
        current_rule = calculate_closing(
            window_incomes=window_incomes,
            income=Decimal("0.00"),
            box_status=box.status,
            retention_pct=box.retention_pct,
            box_balance=box.balance,
            account_balance=Decimal("0.00"),
        )
        last_closing = self.smoothing_box_repository.get_last_closing(box.id)

        return SmoothingBoxDTO.box_to_dict(box, current_rule, last_closing, self._next_reference_date(box, last_closing))

    def _next_reference_date(self, box: SmoothingBox, last_closing: Optional[DailyClosing] = None) -> date:
        if last_closing is None:
            last_closing = self.smoothing_box_repository.get_last_closing(box.id)

        if last_closing is None:
            return box.activated_on

        return last_closing.reference_date + timedelta(days=1)

    def _get_box(self, account: Account, for_update: bool = False) -> SmoothingBox:
        box = self.smoothing_box_repository.get_by_account(account.id, for_update=for_update)

        if box is None:
            raise NotFoundSmoothingBox(account.id)

        return box

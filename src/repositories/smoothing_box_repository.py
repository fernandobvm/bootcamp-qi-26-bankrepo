from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func

from database import Context
from models import BoxEntry, DailyClosing, LedgerEntry, SmoothingBox


class SmoothingBoxRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_account(self, account_id: UUID, for_update: bool = False) -> Optional[SmoothingBox]:
        query = self.session.query(SmoothingBox).filter(SmoothingBox.account_id == account_id)

        if for_update:
            query = query.with_for_update()

        return query.first()

    def create(self, account_id: UUID, retention_pct: int, activated_on: date) -> SmoothingBox:
        box = SmoothingBox()
        box.account_id = account_id
        box.retention_pct = retention_pct
        box.status = SmoothingBox.ACTIVE
        box.balance = Decimal("0.00")
        box.activated_on = activated_on

        self.session.add(box)
        self.session.flush()

        return box

    def update(self, box: SmoothingBox, retention_pct: Optional[int], status: Optional[str]) -> None:
        if retention_pct is not None:
            box.retention_pct = retention_pct

        if status is not None:
            box.status = status

        box.updated_at = func.now()

    def add_entry(
        self, box: SmoothingBox, transaction_id: UUID, direction: str, origin: str, value: Decimal
    ) -> BoxEntry:
        if direction == LedgerEntry.CREDITO:
            box.balance = box.balance + value
        else:
            box.balance = box.balance - value

        box.updated_at = func.now()

        entry = BoxEntry()
        entry.box_id = box.id
        entry.transaction_id = transaction_id
        entry.direction = direction
        entry.origin = origin
        entry.value = value
        entry.balance_after = box.balance

        self.session.add(entry)
        return entry

    def get_entry_by_transaction(self, transaction_id: UUID) -> Optional[BoxEntry]:
        return self.session.query(BoxEntry).filter(BoxEntry.transaction_id == transaction_id).first()

    def get_closing(self, box_id: UUID, reference_date: date) -> Optional[DailyClosing]:
        return (
            self.session.query(DailyClosing)
            .filter(DailyClosing.box_id == box_id, DailyClosing.reference_date == reference_date)
            .first()
        )

    def get_last_closing(self, box_id: UUID) -> Optional[DailyClosing]:
        return (
            self.session.query(DailyClosing)
            .filter(DailyClosing.box_id == box_id)
            .order_by(DailyClosing.reference_date.desc())
            .first()
        )

    def get_window_incomes(self, box_id: UUID, before: Optional[date], window_size: int) -> List[Decimal]:
        query = self.session.query(DailyClosing.income).filter(DailyClosing.box_id == box_id)

        if before is not None:
            query = query.filter(DailyClosing.reference_date < before)

        rows = query.order_by(DailyClosing.reference_date.desc()).limit(window_size).all()

        return [row.income for row in rows]

    def add_closing(self, box_id: UUID, reference_date: date, result: dict, transaction_id: Optional[UUID]) -> DailyClosing:
        closing = DailyClosing()
        closing.box_id = box_id
        closing.reference_date = reference_date
        closing.income = result["income"]
        closing.baseline = result["baseline"]
        closing.window_days = result["window_days"]
        closing.lower_bound = result["lower_bound"]
        closing.upper_bound = result["upper_bound"]
        closing.band = result["band"]
        closing.amount_calculated = result["amount_calculated"]
        closing.amount_moved = result["amount_moved"]
        closing.transaction_id = transaction_id

        self.session.add(closing)
        self.session.flush()

        return closing

    def list_closings(
        self, box_id: UUID, limit: int, offset: int, start_date: Optional[date], end_date: Optional[date]
    ) -> List[DailyClosing]:
        query = self.session.query(DailyClosing).filter(DailyClosing.box_id == box_id)

        if start_date is not None:
            query = query.filter(DailyClosing.reference_date >= start_date)

        if end_date is not None:
            query = query.filter(DailyClosing.reference_date <= end_date)

        return query.order_by(DailyClosing.reference_date.desc()).limit(limit + 1).offset(offset).all()

from typing import List, Optional

from dtos.formatters import money
from models import BoxEntry, DailyClosing, LedgerEntry, SmoothingBox, Transaction


class SmoothingBoxDTO:
    @staticmethod
    def box_to_dict(box: SmoothingBox, current_rule: dict, last_closing: Optional[DailyClosing], next_date) -> dict:
        if last_closing is not None:
            last_closed_date = last_closing.reference_date.isoformat()
        else:
            last_closed_date = None

        return {
            "box_key": str(box.box_key),
            "account_id": str(box.account_id),
            "status": box.status,
            "retention_pct": box.retention_pct,
            "balance": money(box.balance),
            "activated_on": box.activated_on.isoformat(),
            "last_closed_date": last_closed_date,
            "next_reference_date": next_date.isoformat(),
            "baseline": money(current_rule["baseline"]),
            "window_days": current_rule["window_days"],
            "lower_bound": money(current_rule["lower_bound"]),
            "upper_bound": money(current_rule["upper_bound"]),
        }

    @staticmethod
    def closing_to_dict(closing: DailyClosing) -> dict:
        if closing.transaction_id is not None:
            transaction_id = str(closing.transaction_id)
        else:
            transaction_id = None

        return {
            "closing_key": str(closing.closing_key),
            "reference_date": closing.reference_date.isoformat(),
            "income": money(closing.income),
            "baseline": money(closing.baseline),
            "window_days": closing.window_days,
            "lower_bound": money(closing.lower_bound),
            "upper_bound": money(closing.upper_bound),
            "band": closing.band,
            "amount_calculated": money(closing.amount_calculated),
            "amount_moved": money(closing.amount_moved),
            "transaction_id": transaction_id,
        }

    @staticmethod
    def list_closings_to_list_dict(closings: List[DailyClosing]) -> List[dict]:
        closings_list = []

        for closing in closings:
            closings_list.append(SmoothingBoxDTO.closing_to_dict(closing))

        return closings_list

    @staticmethod
    def withdrawal_to_dict(transaction: Transaction, box_entry: BoxEntry, ledger_entry: LedgerEntry) -> dict:
        return {
            "transaction_id": str(transaction.id),
            "value": money(transaction.value),
            "box_balance": money(box_entry.balance_after),
            "account_balance": money(ledger_entry.balance_after),
        }

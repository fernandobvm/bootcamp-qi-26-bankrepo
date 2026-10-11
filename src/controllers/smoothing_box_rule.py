from decimal import ROUND_DOWN, Decimal
from typing import List

from models import DailyClosing, SmoothingBox

WINDOW_DAYS = 28
WARMUP_DAYS = 14
UPPER_FACTOR = Decimal("1.10")
LOWER_FACTOR = Decimal("0.90")
BOX_CAP_FACTOR = Decimal("10")

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_DOWN)


def calculate_closing(
    window_incomes: List[Decimal],
    income: Decimal,
    box_status: str,
    retention_pct: int,
    box_balance: Decimal,
    account_balance: Decimal,
) -> dict:
    window_days = len(window_incomes)

    if window_days > 0:
        baseline = to_cents(sum(window_incomes, ZERO) / window_days)
    else:
        baseline = ZERO

    upper_bound = to_cents(baseline * UPPER_FACTOR)
    lower_bound = to_cents(baseline * LOWER_FACTOR)

    result = {
        "income": income,
        "baseline": baseline,
        "window_days": window_days,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "band": DailyClosing.NEUTRAL,
        "amount_calculated": ZERO,
        "amount_moved": ZERO,
    }

    if window_days < WARMUP_DAYS:
        result["band"] = DailyClosing.WARMUP
        return result

    if box_status == SmoothingBox.PAUSED:
        result["band"] = DailyClosing.PAUSED
        return result

    if baseline == ZERO:
        return result

    if income > upper_bound:
        amount_calculated = to_cents((income - upper_bound) * retention_pct / Decimal(100))
        box_room = max(to_cents(baseline * BOX_CAP_FACTOR) - box_balance, ZERO)

        result["band"] = DailyClosing.ABOVE
        result["amount_calculated"] = amount_calculated
        result["amount_moved"] = min(amount_calculated, box_room, account_balance)
        return result

    if income < lower_bound:
        amount_calculated = lower_bound - income

        result["band"] = DailyClosing.BELOW
        result["amount_calculated"] = amount_calculated
        result["amount_moved"] = min(amount_calculated, box_balance)
        return result

    return result

from decimal import ROUND_HALF_UP, Decimal

from constants import FREE_TRANSFERS_PER_MONTH, TRANSFER_FEE_MINIMUM, TRANSFER_FEE_RATE


def calculate_transfer_fee(value: Decimal, transfers_this_month: int) -> Decimal:
    
    if transfers_this_month < FREE_TRANSFERS_PER_MONTH:
        return Decimal("0.00")

    percentage_fee = (value * TRANSFER_FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return max(percentage_fee, TRANSFER_FEE_MINIMUM)

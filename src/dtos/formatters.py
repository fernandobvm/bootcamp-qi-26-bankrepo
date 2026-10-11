from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from constants import BANK_TIMEZONE


def money(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None

    return f"{value:.2f}"


def bank_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None

    return value.astimezone(ZoneInfo(BANK_TIMEZONE)).isoformat()

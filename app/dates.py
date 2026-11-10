"""Rules about which dates an expense may have: never in the future."""
from datetime import date
from typing import Optional


def is_future_date(year: int, month: int, day: int, today: Optional[date] = None) -> bool:
    """Variable expenses may be dated up to and including today."""
    return date(year, month, day) > (today or date.today())


def is_future_month(year: int, month: int, today: Optional[date] = None) -> bool:
    """Regular expenses may belong to any month up to and including the current one."""
    today = today or date.today()
    return (year, month) > (today.year, today.month)

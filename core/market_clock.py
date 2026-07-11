from datetime import datetime, time
from zoneinfo import ZoneInfo


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

MARKET_OPEN_TIME = time(9, 15)
NEW_ENTRY_CUTOFF_TIME = time(15, 0)
MARKET_CLOSE_TIME = time(15, 30)


def now_in_india() -> datetime:
    return datetime.now(INDIA_TIMEZONE)


def is_weekday(current_time: datetime) -> bool:
    return current_time.weekday() < 5


def is_market_open(current_time: datetime = None) -> bool:
    current_time = current_time or now_in_india()

    if not is_weekday(current_time):
        return False

    current_clock_time = current_time.time()

    return (
        MARKET_OPEN_TIME
        <= current_clock_time
        < MARKET_CLOSE_TIME
    )


def can_open_new_trade(current_time: datetime = None) -> bool:
    current_time = current_time or now_in_india()

    if not is_weekday(current_time):
        return False

    current_clock_time = current_time.time()

    return (
        MARKET_OPEN_TIME
        <= current_clock_time
        < NEW_ENTRY_CUTOFF_TIME
    )


def should_exit_all_positions(
    current_time: datetime = None,
) -> bool:
    current_time = current_time or now_in_india()

    if not is_weekday(current_time):
        return False

    return current_time.time() >= MARKET_CLOSE_TIME


def market_status(current_time: datetime = None) -> str:
    current_time = current_time or now_in_india()

    if not is_weekday(current_time):
        return "CLOSED_WEEKEND"

    current_clock_time = current_time.time()

    if current_clock_time < MARKET_OPEN_TIME:
        return "PRE_MARKET"

    if current_clock_time < NEW_ENTRY_CUTOFF_TIME:
        return "OPEN"

    if current_clock_time < MARKET_CLOSE_TIME:
        return "NO_NEW_ENTRIES"

    return "CLOSED"


if __name__ == "__main__":
    current_time = now_in_india()

    print("India time:", current_time.strftime("%Y-%m-%d %H:%M:%S"))
    print("Market status:", market_status(current_time))
    print("Market open:", is_market_open(current_time))
    print("Can open new trade:", can_open_new_trade(current_time))
    print(
        "Should exit all positions:",
        should_exit_all_positions(current_time),
    )
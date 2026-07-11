from growwapi import GrowwAPI
from config import config

groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)

print("Testing Quote...")

quote = groww.get_quote(
    "RELIANCE",
    groww.EXCHANGE_NSE,
    groww.SEGMENT_CASH
)

print(quote)

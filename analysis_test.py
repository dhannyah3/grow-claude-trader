from growwapi import GrowwAPI
from anthropic import Anthropic
from config import config
import json

groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)
claude = Anthropic(api_key=config.ANTHROPIC_API_KEY)

quote = groww.get_quote(
    "RELIANCE",
    groww.EXCHANGE_NSE,
    groww.SEGMENT_CASH
)

prompt = f"""
You are a quantitative trading analysis assistant.

Use only the market data provided below.

Stock: RELIANCE
Last Price: {quote.get('last_price')}
Day Change: {quote.get('day_change')}
Day Change Percentage: {quote.get('day_change_perc')}
Open: {quote.get('ohlc', {}).get('open')}
High: {quote.get('ohlc', {}).get('high')}
Low: {quote.get('ohlc', {}).get('low')}
Previous Close: {quote.get('ohlc', {}).get('close')}
Volume: {quote.get('volume')}

Rules:
- Do not invent support or resistance levels.
- Do not predict future prices.
- Do not recommend a live trade.
- If the data is insufficient, say so.
- Return only valid JSON.
- Confidence must be an integer from 0 to 100.
- Action must be one of: WATCH, IGNORE, or INSUFFICIENT_DATA.

Return exactly this structure:

{{
  "trend": "",
  "momentum": "",
  "confidence": 0,
  "action": "",
  "reason": ""
}}
"""

response = claude.messages.create(
    model="claude-haiku-4-5",
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

raw_text = response.content[0].text.strip()

if raw_text.startswith("```json"):
    raw_text = raw_text[7:]

if raw_text.startswith("```"):
    raw_text = raw_text[3:]

if raw_text.endswith("```"):
    raw_text = raw_text[:-3]

raw_text = raw_text.strip()
try:
    analysis = json.loads(raw_text)

    print("Stock: RELIANCE")
    print(f"Last price: {quote.get('last_price')}")
    print(f"Trend: {analysis.get('trend')}")
    print(f"Momentum: {analysis.get('momentum')}")
    print(f"Confidence: {analysis.get('confidence')}")
    print(f"Action: {analysis.get('action')}")
    print(f"Reason: {analysis.get('reason')}")

except json.JSONDecodeError:
    print("Claude did not return valid JSON.")
    print("Raw response:")
    print(raw_text)

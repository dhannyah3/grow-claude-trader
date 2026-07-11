import json
from typing import Any, Dict

from anthropic import Anthropic

from config import config


class ClaudeAnalyzer:
    def __init__(self):
        self.client = Anthropic(
            api_key=config.ANTHROPIC_API_KEY,
        )

    def review_setup(
        self,
        symbol: str,
        setup: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = f"""
You are reviewing a paper-trading setup.

Use only the supplied information. Do not invent prices,
support, resistance, news, or market conditions.

Symbol: {symbol}
Price: {setup.get("price")}
Score: {setup.get("score")}
RSI: {setup.get("rsi")}
ATR: {setup.get("atr")}
EMA 20: {setup.get("ema_20")}
EMA 50: {setup.get("ema_50")}
VWAP: {setup.get("vwap")}
MACD: {setup.get("macd")}
MACD Signal: {setup.get("macd_signal")}
Opening Range High: {setup.get("opening_high")}

Return only valid JSON using this structure:

{{
  "approved": false,
  "confidence": 0,
  "reason": ""
}}

Rules:
- approved must be true or false.
- confidence must be an integer from 0 to 100.
- Reject the setup when information is missing or conflicting.
- Do not give financial advice.
"""

        response = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        raw_text = response.content[0].text.strip()

        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]

        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        raw_text = raw_text.strip()

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            return {
                "approved": False,
                "confidence": 0,
                "reason": "Claude returned invalid JSON.",
            }

        approved = bool(result.get("approved", False))

        try:
            confidence = int(result.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0

        confidence = max(0, min(100, confidence))

        return {
            "approved": approved,
            "confidence": confidence,
            "reason": str(result.get("reason", "")),
        }


if __name__ == "__main__":
    analyzer = ClaudeAnalyzer()

    test_setup = {
        "price": 1310.0,
        "score": 85,
        "rsi": 63.5,
        "atr": 2.4,
        "ema_20": 1307.0,
        "ema_50": 1303.0,
        "vwap": 1305.0,
        "macd": 1.6,
        "macd_signal": 1.2,
        "opening_high": 1308.0,
    }

    result = analyzer.review_setup(
        symbol="RELIANCE",
        setup=test_setup,
    )

    print("\n===== CLAUDE SETUP REVIEW =====\n")
    print(result)
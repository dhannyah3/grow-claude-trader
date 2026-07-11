from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    GROWW_ACCESS_TOKEN = os.getenv("GROWW_ACCESS_TOKEN")
    GROWW_TOTP_SECRET = os.getenv("GROWW_TOTP_SECRET")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

config = Config()

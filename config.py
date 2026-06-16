import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Safety Defaults
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
LIVE_TRADING = os.getenv("LIVE_TRADING", "False").lower() == "true"
CONFIRM_LIVE_TRADING = os.getenv("CONFIRM_LIVE_TRADING", "")

# Validation for live trading
IF_LIVE_TRADING_ENABLED = (
    LIVE_TRADING and CONFIRM_LIVE_TRADING == "I_UNDERSTAND_THE_RISK"
)

# APIs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# T212
T212_API_KEY = os.getenv("T212_API_KEY")

# DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./t212_lab.db")

# Watchlist
DEFAULT_WATCHLIST = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", 
    "AMD", "META", "GOOGL", "AMZN", "TSLA", "PLTR"
]

# Risk Parameters
MAX_RISK_PER_TRADE = 0.01  # 1%
MAX_EXPOSURE_PER_TICKER = 0.05  # 5%
MAX_TOTAL_EXPOSURE = 0.30  # 30%

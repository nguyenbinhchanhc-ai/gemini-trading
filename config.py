import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# App environment
PORT = int(os.getenv("PORT", 10000))
APP_ENV = os.getenv("APP_ENV", "production")

# Gemini Web-to-API config
# Trỏ trực tiếp tới Go proxy chạy ở background (cổng 4981)
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "http://localhost:4981/openai/v1")
# Vì proxy không cần API key thực tế, ta sử dụng chuỗi mock
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "not-needed")
# Model mặc định cho gemini-web-to-api
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-advanced")

# OKX API credentials
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
OKX_API_PASSWORD = os.getenv("OKX_API_PASSWORD", "")
OKX_USE_DEMO = os.getenv("OKX_USE_DEMO", "true").lower() == "true"

# Trading Settings
TRADE_SYMBOL = os.getenv("TRADE_SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "1h")
ANALYSIS_INTERVAL_MINUTES = int(os.getenv("ANALYSIS_INTERVAL_MINUTES", 60))

# Gemini Official API key (for fallback/primary high stability)
GEMINI_OFFICIAL_API_KEY = os.getenv("GEMINI_OFFICIAL_API_KEY", "")
GEMINI_OFFICIAL_MODEL = os.getenv("GEMINI_OFFICIAL_MODEL", "gemini-1.5-pro")

# Paper trading initial balance (Giả lập số dư ban đầu bằng USD)
INITIAL_PAPER_BALANCE = 10000.0
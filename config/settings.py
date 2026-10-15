import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGO_URI = os.getenv("MONGO_URI", "")
    LOGMUX_TOKEN = os.getenv("LOGMUX_TOKEN", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "500"))
    TRADING_SYMBOLS = os.getenv("TRADING_SYMBOLS", "RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ICICIBANK.NS").split(",")
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
    RSI_OVERBOUGHT = int(os.getenv("RSI_OVERBOUGHT", "70"))
    RSI_OVERSOLD = int(os.getenv("RSI_OVERSOLD", "30"))
    MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "0.1"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

settings = Settings()
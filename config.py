import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BNS_UUID = os.getenv("BNS_UUID")
    MONGODB_SETTINGS_HOST = os.getenv("MONGODB_SETTINGS_HOST")
    PORT = os.getenv("PORT", "5000")
    
    raw_portfolio_ids = os.getenv("PORTFOLIO_IDS", "")
    if raw_portfolio_ids:
        PORTFOLIO_IDS = [pid.strip() for pid in raw_portfolio_ids.split(',')]
    else:
        PORTFOLIO_IDS = []

if __name__ == '__main__':
    print(f"BNS_UUID: {Config.BNS_UUID}")
    print(f"MONGODB_SETTINGS_HOST: {Config.MONGODB_SETTINGS_HOST}")
    print(f"PORT: {Config.PORT}")
    print(f"PORTFOLIO_IDS: {Config.PORTFOLIO_IDS}")

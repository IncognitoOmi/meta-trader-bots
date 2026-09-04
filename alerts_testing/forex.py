import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime
import pytz
import requests

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"

# YAHI HAI FOREX GOLD KA TICKER
SYMBOL = "XAUUSD=X" 

# =============== DATA FETCH AGENT =================
class DataAgent:
    def run(self):
        try:
            # period="5d" rakha hai taaki weekend par bhi last Friday ka price dikhe
            # interval="1m" chahiye tujhe
            data = yf.download(tickers=SYMBOL, interval="1m", period="5d", progress=False)

            if data.empty:
                print(f"⚠️ Yahoo ne data nahi diya {SYMBOL} ke liye.")
                return pd.DataFrame()

            # Cleaning Data
            df = data.reset_index()
            df.columns = [c.lower() for c in df.columns]

            # Column renaming fix
            if 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'timestamp'})
            elif 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            
            # Price extraction
            df["close"] = df["close"].astype(float)
            return df[["timestamp", "close"]]

        except Exception as e:
            print(f"Error: {e}")
            return pd.DataFrame()

# =============== RSI AGENT =================
class RSIAgent:
    def run(self, df):
        if df.empty: return df
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
        
        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

# =============== EMA AGENT =================
class EMAAgent:
    def run(self, df):
        if df.empty: return df
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        return df

# =============== MAIN LOOP =================
if __name__ == "__main__":
    print(f"🤖 Trying to fetch Forex Gold ({SYMBOL})...")
    
    data_agent = DataAgent()
    rsi_agent = RSIAgent()
    ema_agent = EMAAgent()

    while True:
        df = data_agent.run()
        
        if not df.empty:
            df = rsi_agent.run(df)
            df = ema_agent.run(df)
            
            last = df.iloc[-1]
            print(f"🟢 Price: {last['close']:.2f} | RSI: {last['rsi']:.2f} | Time: {last['timestamp']}")
        else:
            print("❌ Yahoo API se data nahi aa raha. (Yahoo issue)")
        
        time.sleep(60)
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"
TARGET_PAIR = "PAXGUSDT"   # Sirf Gold ke liye setting
LOOP_SLEEP_SECONDS = 3   # Check signals every 2 minutes

# =============== BASE AGENT =================
class BaseAgent:
    def run(self, *args, **kwargs):
        raise NotImplementedError

# =============== DATA FETCH AGENT =================
class DataAgent(BaseAgent):
    def __init__(self, interval="5m", limit=1000): # Limit 200 is enough for EMA 200
        self.interval = interval
        self.limit = limit
        self.symbol = ""

    def run(self):
        url = "https://api.binance.com/api/v3/klines"
        params = { "symbol": self.symbol, "interval": self.interval, "limit": self.limit }
        try:
            response = requests.get(url, params=params)
            if response.status_code != 200: return pd.DataFrame()
            
            data = response.json()
            df = pd.DataFrame(data, columns=[
                "timestamp","open","high","low","close","volume",
                "close_time","quote_asset_volume","num_trades",
                "taker_buy_base","taker_buy_quote","ignore"
            ])
            df["close"] = df["close"].astype(float)
            return df[["close"]]
        except:
            return pd.DataFrame()

# =============== RSI AGENT =================
class RSIAgent(BaseAgent):
    def __init__(self, window=14):
        self.window = window

    def run(self, df: pd.DataFrame):
        if df.empty: return df
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/self.window, min_periods=self.window).mean()
        avg_loss = loss.ewm(alpha=1/self.window, min_periods=self.window).mean()
        
        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

# =============== EMA AGENT =================
class EMAAgent(BaseAgent):
    def __init__(self, span=200):
        self.span = span

    def run(self, df: pd.DataFrame):
        if df.empty: return df
        df["ema_200"] = df["close"].ewm(span=self.span, adjust=False).mean()
        return df

# =============== ALERT AGENT =================
class AlertAgent(BaseAgent):
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.ist = pytz.timezone("Asia/Kolkata")

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.chat_id, "text": message})
        except: pass

    def run(self, df: pd.DataFrame, symbol):
        if df.empty: return
        
        latest = df.iloc[-1]
        price = latest["close"]
        rsi = latest["rsi"]
        ema_200 = latest["ema_200"]
        now = datetime.now(self.ist).strftime("%I:%M %p")

        if pd.isna(rsi) or pd.isna(ema_200): return

        # LOGIC
        signal = None
        if price > ema_200 and rsi <= 35:
            signal = "BUY"
            icon = "🟢"
        elif price < ema_200 and rsi >= 65:
            signal = "SELL"
            icon = "🔴"

        # 1. PRINT STATUS TO CONSOLE (Clean format)
        print(f"{now} | {symbol: <10} | Price: {price:.2f} | RSI: {rsi:.2f} | EMA: {ema_200:.2f} | {signal if signal else 'No Signal'}")

        # 2. SEND TELEGRAM IF SIGNAL
        if signal:
            msg = (f"{icon} {signal} SIGNAL - {symbol}\n"
                   f"Price: {price}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"EMA: {ema_200:.2f}\n"
                   f"Time: 5m")
            self.send_telegram(msg)
            print(f"   >>> ALERT SENT FOR {symbol} <<<")

# =============== ORCHESTRATOR =================
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        # Ab hume VolumeFilterAgent ki zaroorat nahi hai
        self.data_agent = DataAgent()
        self.rsi_agent = RSIAgent()
        self.ema_agent = EMAAgent()
        self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
        
        # Sirf ek hi symbol list me daal diya
        self.active_symbols = [TARGET_PAIR]

    def run(self):
        # Volume Scanning wala part hata diya hai
        # Direct signal check karenge
        
        print(f"--- 📊 Checking {TARGET_PAIR} ({datetime.now().strftime('%H:%M:%S')}) ---")
        for symbol in self.active_symbols:
            self.data_agent.symbol = symbol
            df = self.data_agent.run()
            df = self.rsi_agent.run(df)
            df = self.ema_agent.run(df)
            self.alert_agent.run(df, symbol)

# =============== MAIN =================
if __name__ == "__main__":
    bot = OrchestratorAgent()
    print(f"Bot Starting for {TARGET_PAIR} Only...")
    
    while True:
        try:
            bot.run()
            print(f"\nCycle Done. Sleeping {LOOP_SLEEP_SECONDS} seconds...\n" + "="*50 + "\n")
            time.sleep(LOOP_SLEEP_SECONDS)
        except KeyboardInterrupt:
            print("Bot Stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"

TARGET_SYMBOLS = ["PAXGUSDT"]
LOOP_SLEEP_SECONDS = 3

# =============== BASE AGENT =================
class BaseAgent:
    def run(self, *args, **kwargs):
        raise NotImplementedError

# =============== DATA FETCH AGENT =================
class DataAgent(BaseAgent):
    def __init__(self, interval="1m", limit=1000): 
        self.interval = interval
        self.limit = limit
        self.symbol = ""

    def run(self):
        url = "https://api.binance.com/api/v3/klines"
        params = { "symbol": self.symbol, "interval": self.interval, "limit": self.limit }
        try:
            response = requests.get(url, params=params)
            if response.status_code != 200: 
                return pd.DataFrame()
            
            data = response.json()
            if not isinstance(data, list): 
                return pd.DataFrame()

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

# =============== EMA 400 AGENT =================
class EMAAgent(BaseAgent):
    def __init__(self, span=400):
        self.span = span

    def run(self, df: pd.DataFrame):
        if df.empty: return df
        df["ema_400"] = df["close"].ewm(span=self.span, adjust=False).mean()
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
        except:
            pass

    def run(self, df: pd.DataFrame, symbol):
        if df.empty:
            print(f"Skipping {symbol}: No Data")
            return
        
        latest = df.iloc[-1]
        price = latest["close"]
        rsi = latest["rsi"]
        ema_400 = latest["ema_400"]
        now = datetime.now(self.ist).strftime("%I:%M %p")

        if pd.isna(rsi) or pd.isna(ema_400):
            return

        signal = None

        # ===== 400 EMA LOGIC =====
        if price > ema_400 and rsi <= 35:
            signal = "BUY"
            icon = "🟢"
        elif price < ema_400 and rsi >= 65:
            signal = "SELL"
            icon = "🔴"

        print(f"{now} | {symbol:<10} | Price: {price:.2f} | RSI: {rsi:.2f} | EMA400: {ema_400:.2f} | {signal if signal else 'No Signal'}")

        if signal:
            msg = (f"{icon} {signal} SIGNAL - {symbol}\n"
                   f"Price: {price}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"EMA 400: {ema_400:.4f}\n"
                   f"Time: {now}\n"
                   f"Timeframe: 1m")
            self.send_telegram(msg)
            print(f"   >>> ALERT SENT FOR {symbol} <<<")

# =============== ORCHESTRATOR =================
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        self.data_agent = DataAgent(interval="1m") 
        self.rsi_agent = RSIAgent()
        self.ema_agent = EMAAgent(span=400)
        self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
        self.active_symbols = TARGET_SYMBOLS

    def run(self):
        print(f"--- 📊 Checking Signals ({datetime.now().strftime('%H:%M:%S')}) ---")
        for symbol in self.active_symbols:
            self.data_agent.symbol = symbol
            df = self.data_agent.run()
            df = self.rsi_agent.run(df)
            df = self.ema_agent.run(df)
            self.alert_agent.run(df, symbol)
            time.sleep(0.1)

# =============== MAIN =================
if __name__ == "__main__":
    bot = OrchestratorAgent()
    print(f"Bot Starting for {TARGET_SYMBOLS} on 1m Timeframe (EMA 400)...")
    
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

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"
MIN_VOLUME_USDT = 100_000_00  # Filter: 100 Million USDT
REFRESH_VOLUME_MINUTES = 60    # Re-scan volume list every 60 minutes
LOOP_SLEEP_SECONDS = 180       # Check signals every 2 minutes

# =============== BASE AGENT =================
class BaseAgent:
    def run(self, *args, **kwargs):
        raise NotImplementedError

# =============== VOLUME FILTER AGENT =================
class VolumeFilterAgent(BaseAgent):
    def __init__(self, min_volume):
        self.min_volume = min_volume

    def run(self):
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            high_volume_symbols = []
            for item in data:
                symbol = item['symbol']
                if symbol.endswith("USDT"):
                    quote_vol = float(item['quoteVolume'])
                    if quote_vol > self.min_volume:
                        high_volume_symbols.append(symbol)
            
            # Sort alphabetically or by volume (optional), returning just list
            return high_volume_symbols
        except Exception as e:
            print(f"Error fetching volume list: {e}")
            return []

# =============== DATA FETCH AGENT =================
class DataAgent(BaseAgent):
    def __init__(self, interval="5m", limit=1000): 
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
        if price > ema_200 and rsi <= 31:
            signal = "BUY"
            icon = "🟢"
        elif price < ema_200 and rsi >= 69:
            signal = "SELL"
            icon = "🔴"

        # 1. PRINT STATUS TO CONSOLE (Clean format: Time | Symbol | Price | RSI | EMA | Signal)
        print(f"{now} | {symbol: <10} | Price: {price:.4f} | RSI: {rsi:.2f} | EMA: {ema_200:.4f} | {signal if signal else 'No Signal'}")

        # 2. SEND TELEGRAM IF SIGNAL
        if signal:
            msg = (f"{icon} {signal} SIGNAL - {symbol}\n"
                   f"Price: {price}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"EMA: {ema_200:.4f}\n"
                   f"Time: {now}")
            self.send_telegram(msg)
            print(f"   >>> ALERT SENT FOR {symbol} <<<")

# =============== ORCHESTRATOR =================
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        self.volume_agent = VolumeFilterAgent(MIN_VOLUME_USDT)
        self.data_agent = DataAgent()
        self.rsi_agent = RSIAgent()
        self.ema_agent = EMAAgent()
        self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
        self.active_symbols = []
        self.last_scan_time = 0

    def run(self):
        # 1. Update Volume List every X minutes (or if empty)
        if time.time() - self.last_scan_time > (REFRESH_VOLUME_MINUTES * 60) or not self.active_symbols:
            print(f"\n--- 🔍 Scanning Top Volume Pairs (> {MIN_VOLUME_USDT/1_000_000:,.0f}M USDT) ---")
            self.active_symbols = self.volume_agent.run()
            self.last_scan_time = time.time()
            print(f"Found {len(self.active_symbols)} active pairs. Starting analysis...\n")
        
        # 2. Check Signals for current list
        print(f"--- 📊 Checking Signals ({datetime.now().strftime('%H:%M:%S')}) ---")
        for symbol in self.active_symbols:
            self.data_agent.symbol = symbol
            df = self.data_agent.run()
            df = self.rsi_agent.run(df)
            df = self.ema_agent.run(df)
            self.alert_agent.run(df, symbol)
            time.sleep(0.05) # Tiny sleep

# =============== MAIN =================
if __name__ == "__main__":
    bot = OrchestratorAgent()
    print("Bot Starting...")
    
    while True:
        try:
            bot.run()
            print(f"\nCycle Done. Sleeping {LOOP_SLEEP_SECONDS/60} mins...\n" + "="*50 + "\n")
            time.sleep(LOOP_SLEEP_SECONDS)
        except KeyboardInterrupt:
            print("Bot Stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
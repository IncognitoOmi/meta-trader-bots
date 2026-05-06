import MetaTrader5 as mt5
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"

# LIST OF PAIRS TO MONITOR (Must match MT5 Market Watch exactly)
TARGET_SYMBOLS = ["XAUUSD"]#, "NDX100", "DJI30"]#"EURUSD"],"AUDUSD","GBPUSD"] 

LOOP_SLEEP_SECONDS = 5        # Check every 5s to catch 1m candles

# =============== BASE AGENT =================
class BaseAgent:
    def run(self, *args, **kwargs):
        raise NotImplementedError

# =============== DATA FETCH AGENT (MT5) =================
class DataAgent(BaseAgent):
    def __init__(self, timeframe=mt5.TIMEFRAME_M1, limit=1000): 
        self.timeframe = timeframe
        self.limit = limit
        self.symbol = ""

    def run(self):
        # Fetch rates from MT5
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.limit)
        
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        return df[["close"]]

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
        if df.empty: 
            print(f"Skipping {symbol}: No Data found (Check if pair exists in MT5 Market Watch)")
            return
        
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

        # 1. PRINT STATUS TO CONSOLE
        print(f"{now} | {symbol: <10} | Price: {price:.2f} | RSI: {rsi:.2f} | EMA: {ema_200:.2f} | {signal if signal else 'No Signal'}")

        # 2. SEND TELEGRAM IF SIGNAL
        if signal:
            msg = (f"{icon} {signal} SIGNAL - {symbol}\n"
                   f"Price: {price}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"EMA: {ema_200:.4f}\n"
                   f"Time: {now}\n"
                   f"Timeframe: 1m")
            self.send_telegram(msg)
            print(f"   >>> ALERT SENT FOR {symbol} <<<")

# =============== NEWS AGENT =================
class NewsAgent(BaseAgent):
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.target_currencies = ["USD", "AUD", "EUR", "GBP"]
        self.alerted = set() 
        self.last_fetch = 0
        self.news_data = []

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.chat_id, "text": message})
        except: pass

    def fetch_news(self):
        # Fetch data every 4 hours to avoid rate limits/IP blocks
        if time.time() - self.last_fetch > 14400:
            try:
                resp = requests.get(self.url)
                self.news_data = [n for n in resp.json() if n.get("country") in self.target_currencies and n.get("impact") == "High"]
                self.last_fetch = time.time()
                print(">>> News Data Updated from API <<<")
            except Exception as e:
                print(f"News fetch error: {e}")

    def run(self):
        self.fetch_news()
        now = datetime.now(pytz.utc)

        for news in self.news_data:
            try:
                news_time = datetime.fromisoformat(news["date"]).astimezone(pytz.utc)
            except:
                continue
            
            time_diff_mins = (news_time - now).total_seconds() / 60.0
            news_id = f"{news['title']}_{news['date']}"
            
            # Alert 30 mins before
            if 0 < time_diff_mins <= 30 and f"{news_id}_before" not in self.alerted:
                msg = f"🚨 RED FOLDER NEWS ALERT 🚨\n\nCurrency: {news['country']}\nEvent: {news['title']}\nTime Left: {int(time_diff_mins)} Mins Before"
                self.send_telegram(msg)
                self.alerted.add(f"{news_id}_before")
                print(f" >>> NEWS ALERT SENT: {news['title']} (30m Before) <<<")

            # Alert 15 mins after
            elif -15 <= time_diff_mins < 0 and f"{news_id}_after" not in self.alerted:
                msg = f"✅ VOLATILITY SETTLED ✅\n\nCurrency: {news['country']}\nEvent: {news['title']}\nStatus: 15 Mins Passed"
                self.send_telegram(msg)
                self.alerted.add(f"{news_id}_after")
                print(f" >>> NEWS ALERT SENT: {news['title']} (15m After) <<<")

# =============== ORCHESTRATOR =================
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        self.data_agent = DataAgent(timeframe=mt5.TIMEFRAME_M1) 
        self.rsi_agent = RSIAgent()
        self.ema_agent = EMAAgent()
        self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
        self.news_agent = NewsAgent(BOT_TOKEN, CHAT_ID)
        self.active_symbols = TARGET_SYMBOLS

    def run(self):
        # 1. Check News
        self.news_agent.run()

        # 2. Check Signals
        print(f"--- 📊 Checking Signals ({datetime.now().strftime('%H:%M:%S')}) ---")
        for symbol in self.active_symbols:
            self.data_agent.symbol = symbol
            df = self.data_agent.run()
            df = self.rsi_agent.run(df)
            df = self.ema_agent.run(df)
            self.alert_agent.run(df, symbol)
            time.sleep(0.1) # Short delay between pairs

# =============== MAIN =================
if __name__ == "__main__":
    # Connect to the running MT5 terminal
    if not mt5.initialize():
        print(f"MT5 initialization failed. Error: {mt5.last_error()}")
        quit()

    bot = OrchestratorAgent()
    print(f"Bot Starting for {TARGET_SYMBOLS} on 1m Timeframe via MT5...")
    
    try:
        while True:
            bot.run()
            print(f"\nCycle Done. Sleeping {LOOP_SLEEP_SECONDS} seconds...\n" + "="*50 + "\n")
            time.sleep(LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\nBot Stopped by User.")
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
    finally:
        mt5.shutdown()
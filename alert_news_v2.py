# import MetaTrader5 as mt5
# import requests
# import pandas as pd
# import time
# from datetime import datetime
# import pytz

# # ================= CONFIG =================
# BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
# CHAT_ID = "1155443179"
# TARGET_SYMBOLS = ["XAUUSD"] 
# LOOP_SLEEP_SECONDS = 5        

# # Strategy Parameters
# MIN_TRAVEL_PRICE = 8.0
# PRE_ALERT_BUFFER = 1.0  # Alert when price is within $1.00 of the EMA

# # =============== BASE AGENT =================
# class BaseAgent:
#     def run(self, *args, **kwargs):
#         raise NotImplementedError

# # =============== DATA AGENT =================
# class DataAgent(BaseAgent):
#     def __init__(self, timeframe=mt5.TIMEFRAME_M1, limit=500): 
#         self.timeframe = timeframe
#         self.limit = limit
#         self.symbol = ""

#     def run(self):
#         rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.limit)
#         if rates is None or len(rates) == 0:
#             return pd.DataFrame()
#         df = pd.DataFrame(rates)
#         df['time'] = pd.to_datetime(df['time'], unit='s')
#         return df[["time", "open", "high", "low", "close"]]

# # =============== EMA AGENT =================
# class EMAAgent(BaseAgent):
#     def __init__(self, span=200):
#         self.span = span

#     def run(self, df: pd.DataFrame):
#         if df.empty: return df
#         df["ema_200"] = df["low"].ewm(span=self.span, adjust=False).mean()
#         return df

# # =============== ALERT AGENT =================
# class AlertAgent(BaseAgent):
#     def __init__(self, bot_token, chat_id):
#         self.bot_token = bot_token
#         self.chat_id = chat_id
#         self.ist = pytz.timezone("Asia/Kolkata")
#         self.alerted_events = set() # Tracks both "ready" and "exec" alerts

#     def send_telegram(self, message):
#         url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
#         try:
#             requests.post(url, json={"chat_id": self.chat_id, "text": message})
#         except: pass

#     def get_trend_and_distance(self, df):
#         last_closed = df.iloc[-1]
#         trend = "UP" if last_closed['close'] > last_closed['ema_200'] else "DOWN"
#         extreme = last_closed['high'] if trend == "UP" else last_closed['low']

#         for i in range(len(df)-1, -1, -1):
#             curr = df.iloc[i]
#             if trend == "UP":
#                 if curr['close'] <= curr['ema_200']: break
#                 extreme = max(extreme, curr['high'])
#             else:
#                 if curr['close'] >= curr['ema_200']: break
#                 extreme = min(extreme, curr['low'])

#         dist_up = extreme - last_closed['ema_200'] if trend == "UP" else 0
#         dist_dn = last_closed['ema_200'] - extreme if trend == "DOWN" else 0
#         return dist_up, dist_dn

#     def run(self, df: pd.DataFrame, symbol):
#         if df.empty: return
        
#         # Calculate historical distance using completely closed candles (Anti-Breakout check)
#         df_prior = df.iloc[:-1]
#         dist_up, dist_dn = self.get_trend_and_distance(df_prior)
        
#         last_closed = df.iloc[-2]
#         live_candle = df.iloc[-1]
        
#         candle_time = int(last_closed["time"].timestamp())
#         now = datetime.now(self.ist).strftime("%I:%M:%S %p")
        
#         live_price = live_candle["close"]
#         live_ema = live_candle["ema_200"]

#         signal = None
#         icon = ""
#         alert_msg = ""

#         # ================= BUY LOGIC =================
#         if dist_up >= MIN_TRAVEL_PRICE:
#             # 1. EXECUTION CHECK (Did the closed candle touch and reject?)
#             if last_closed['low'] <= last_closed['ema_200'] and last_closed['close'] > last_closed['ema_200']:
#                 if df.iloc[-3]['close'] > df.iloc[-3]['ema_200']: # Anti-breakout filter
#                     alert_id = f"{candle_time}_buy_exec"
#                     if alert_id not in self.alerted_events:
#                         signal = "BUY EXECUTING"
#                         icon = "🟢"
#                         alert_msg = f"{icon} {signal} - {symbol}\nEntry Confirmed @ {last_closed['close']:.2f}\nTime: {now}"
#                         self.alerted_events.add(alert_id)
                        
#             # 2. PRE-ALERT CHECK (Is the live price getting close?)
#             elif live_price > live_ema and (live_price - live_ema) <= PRE_ALERT_BUFFER:
#                 alert_id = f"{candle_time}_buy_ready"
#                 if alert_id not in self.alerted_events:
#                     signal = "GET READY (BUY)"
#                     icon = "⚠️"
#                     alert_msg = f"{icon} {signal} - {symbol}\nPrice is ${live_price - live_ema:.2f} away from EMA!\nEMA: {live_ema:.2f}\nTime: {now}"
#                     self.alerted_events.add(alert_id)

#         # ================= SELL LOGIC =================
#         elif dist_dn >= MIN_TRAVEL_PRICE:
#             # 1. EXECUTION CHECK
#             if last_closed['high'] >= last_closed['ema_200'] and last_closed['close'] < last_closed['ema_200']:
#                 if df.iloc[-3]['close'] < df.iloc[-3]['ema_200']: # Anti-breakout filter
#                     alert_id = f"{candle_time}_sell_exec"
#                     if alert_id not in self.alerted_events:
#                         signal = "SELL EXECUTING"
#                         icon = "🔴"
#                         alert_msg = f"{icon} {signal} - {symbol}\nEntry Confirmed @ {last_closed['close']:.2f}\nTime: {now}"
#                         self.alerted_events.add(alert_id)
                        
#             # 2. PRE-ALERT CHECK
#             elif live_price < live_ema and (live_ema - live_price) <= PRE_ALERT_BUFFER:
#                 alert_id = f"{candle_time}_sell_ready"
#                 if alert_id not in self.alerted_events:
#                     signal = "GET READY (SELL)"
#                     icon = "⚠️"
#                     alert_msg = f"{icon} {signal} - {symbol}\nPrice is ${live_ema - live_price:.2f} away from EMA!\nEMA: {live_ema:.2f}\nTime: {now}"
#                     self.alerted_events.add(alert_id)

#         print(f"{now} | {symbol: <6} | C: {live_price:.2f} | EMA: {live_ema:.2f} | UP: {dist_up:.2f} | DN: {dist_dn:.2f} | {signal if signal else 'Waiting...'}")

#         if signal:
#             self.send_telegram(alert_msg)
#             print(f"   >>> TELEGRAM ALERT SENT: {signal} <<<")

# # =============== NEWS AGENT =================
# class NewsAgent(BaseAgent):
#     def __init__(self, bot_token, chat_id):
#         self.bot_token = bot_token
#         self.chat_id = chat_id
#         self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
#         self.target_currencies = ["USD", "AUD", "EUR", "GBP"]
#         self.alerted = set() 
#         self.last_fetch = 0
#         self.news_data = []

#     def send_telegram(self, message):
#         url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
#         try:
#             requests.post(url, json={"chat_id": self.chat_id, "text": message})
#         except: pass

#     def fetch_news(self):
#         if time.time() - self.last_fetch > 14400:
#             try:
#                 resp = requests.get(self.url)
#                 self.news_data = [n for n in resp.json() if n.get("country") in self.target_currencies and n.get("impact") == "High"]
#                 self.last_fetch = time.time()
#                 print(">>> News Data Updated from API <<<")
#             except Exception as e:
#                 pass

#     def run(self):
#         self.fetch_news()
#         now = datetime.now(pytz.utc)

#         for news in self.news_data:
#             try:
#                 news_time = datetime.fromisoformat(news["date"]).astimezone(pytz.utc)
#             except: continue
            
#             time_diff_mins = (news_time - now).total_seconds() / 60.0
#             news_id = f"{news['title']}_{news['date']}"
            
#             if 0 < time_diff_mins <= 30 and f"{news_id}_before" not in self.alerted:
#                 msg = f"🚨 RED FOLDER NEWS ALERT 🚨\n\nCurrency: {news['country']}\nEvent: {news['title']}\nTime Left: {int(time_diff_mins)} Mins Before"
#                 self.send_telegram(msg)
#                 self.alerted.add(f"{news_id}_before")
            
#             elif -15 <= time_diff_mins < 0 and f"{news_id}_after" not in self.alerted:
#                 msg = f"✅ VOLATILITY SETTLED ✅\n\nCurrency: {news['country']}\nEvent: {news['title']}\nStatus: 15 Mins Passed"
#                 self.send_telegram(msg)
#                 self.alerted.add(f"{news_id}_after")

# # =============== ORCHESTRATOR =================
# class OrchestratorAgent(BaseAgent):
#     def __init__(self):
#         self.data_agent = DataAgent(timeframe=mt5.TIMEFRAME_M1, limit=500) 
#         self.ema_agent = EMAAgent()
#         self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
#         self.news_agent = NewsAgent(BOT_TOKEN, CHAT_ID)
#         self.active_symbols = TARGET_SYMBOLS

#     def run(self):
#         self.news_agent.run()
#         for symbol in self.active_symbols:
#             self.data_agent.symbol = symbol
#             df = self.data_agent.run()
#             df = self.ema_agent.run(df)
#             self.alert_agent.run(df, symbol)
#             time.sleep(0.1) 

# # =============== MAIN =================
# if __name__ == "__main__":
#     if not mt5.initialize():
#         print(f"MT5 initialization failed. Error: {mt5.last_error()}")
#         quit()

#     bot = OrchestratorAgent()
#     print(f"Bot Starting for {TARGET_SYMBOLS} on 1m Timeframe via MT5...")
#     print(f"Active Parameters: Minimum Distance = ${MIN_TRAVEL_PRICE}, Pre-Alert Buffer = ${PRE_ALERT_BUFFER}\n")
    
#     try:
#         while True:
#             bot.run()
#             time.sleep(LOOP_SLEEP_SECONDS)
#     except KeyboardInterrupt:
#         print("\nBot Stopped by User.")
#     finally:
#         mt5.shutdown()


# ================================



import MetaTrader5 as mt5
import requests
import pandas as pd
import time
from datetime import datetime
import pytz
import math

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"
TARGET_SYMBOLS = ["XAUUSD"] 
LOOP_SLEEP_SECONDS = 5        

# Strategy Parameters
MIN_TRAVEL_PRICE = 8.0
PRE_ALERT_BUFFER = 1.0  # Alert when price is within $1.00 of the EMA

# Dynamic Risk Management Configuration
RISK_USD = 100.0
MIN_RR_RATIO = 1.0  # Filter out trades where Reward < Risk (e.g., RR less than 1:1)

# =============== BASE AGENT =================
class BaseAgent:
    def run(self, *args, **kwargs):
        raise NotImplementedError

# =============== DATA AGENT =================
class DataAgent(BaseAgent):
    def __init__(self, timeframe=mt5.TIMEFRAME_M1, limit=500): 
        self.timeframe = timeframe
        self.limit = limit
        self.symbol = ""

    def run(self):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df[["time", "open", "high", "low", "close"]]

# =============== EMA AGENT =================
class EMAAgent(BaseAgent):
    def __init__(self, span=200):
        self.span = span

    def run(self, df: pd.DataFrame):
        if df.empty: return df
        df["ema_200"] = df["low"].ewm(span=self.span, adjust=False).mean()
        return df

# =============== ALERT AGENT =================
class AlertAgent(BaseAgent):
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.ist = pytz.timezone("Asia/Kolkata")
        self.alerted_events = set() # Tracks both "ready" and "exec" alerts

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.chat_id, "text": message})
        except: pass

    def get_trend_and_distance(self, df):
        last_closed = df.iloc[-1]
        trend = "UP" if last_closed['close'] > last_closed['ema_200'] else "DOWN"
        extreme = last_closed['high'] if trend == "UP" else last_closed['low']

        for i in range(len(df)-1, -1, -1):
            curr = df.iloc[i]
            if trend == "UP":
                if curr['close'] <= curr['ema_200']: break
                extreme = max(extreme, curr['high'])
            else:
                if curr['close'] >= curr['ema_200']: break
                extreme = min(extreme, curr['low'])

        dist_up = extreme - last_closed['ema_200'] if trend == "UP" else 0
        dist_dn = last_closed['ema_200'] - extreme if trend == "DOWN" else 0
        return dist_up, dist_dn

    def calc_trade_intelligence(self, entry, trend):
        """
        Calculates dynamic levels based on psychological numbers:
        SL: Closest level divisible by 5
        TP: Closest level divisible by 10
        """
        if trend == "UP":
            sl = math.floor(entry / 5) * 5
            tp = math.ceil(entry / 10) * 10
            risk_pts = entry - sl
            reward_pts = tp - entry
        else: # DOWN
            sl = math.ceil(entry / 5) * 5
            tp = math.floor(entry / 10) * 10
            risk_pts = sl - entry
            reward_pts = entry - tp
            
        risk_pts = max(risk_pts, 0.1) # Guard against division by zero
        rr_ratio = reward_pts / risk_pts
        lot_size = round(1.0 / risk_pts, 2) # Strict Gold $100 risk sizing formula
        
        return sl, tp, risk_pts, rr_ratio, lot_size

    def run(self, df: pd.DataFrame, symbol):
        if df.empty: return
        
        # Calculate historical distance using completely closed candles
        df_prior = df.iloc[:-1]
        dist_up, dist_dn = self.get_trend_and_distance(df_prior)
        
        last_closed = df.iloc[-2]
        live_candle = df.iloc[-1]
        
        candle_time = int(last_closed["time"].timestamp())
        now = datetime.now(self.ist).strftime("%I:%M:%S %p")
        
        live_price = live_candle["close"]
        live_ema = live_candle["ema_200"]
        entry_price = last_closed['close']

        signal = None
        icon = ""
        alert_msg = ""

        # ================= BUY LOGIC =================
        if dist_up >= MIN_TRAVEL_PRICE:
            # 1. EXECUTION CHECK (Did the closed candle touch and reject above 200 EMA?)
            if last_closed['low'] <= last_closed['ema_200'] and last_closed['close'] > last_closed['ema_200']:
                if df.iloc[-3]['close'] > df.iloc[-3]['ema_200']: # Anti-breakout filter
                    sl, tp, risk_pts, rr, lot = self.calc_trade_intelligence(entry_price, "UP")
                    
                    # Risk-to-Reward Smart Filter
                    if rr >= MIN_RR_RATIO:
                        alert_id = f"{candle_time}_buy_exec"
                        if alert_id not in self.alerted_events:
                            signal = "BUY EXECUTING"
                            icon = "🟢"
                            alert_msg = f"{icon} {signal} - {symbol}\nEntry @ {entry_price:.2f}\nSL: {sl:.2f} | TP: {tp:.2f}\nLot: {lot} ($100 Risk)\nRR: 1:{rr:.1f}\nTime: {now}"
                            self.alerted_events.add(alert_id)
                    else:
                        print(f"{now} | Skipped Invalid BUY Setup at {entry_price:.2f} due to poor RR (1:{rr:.1f})")
                        
            # 2. PRE-ALERT CHECK (Is the live price getting close?)
            elif live_price > live_ema and (live_price - live_ema) <= PRE_ALERT_BUFFER:
                alert_id = f"{candle_time}_buy_ready"
                if alert_id not in self.alerted_events:
                    signal = "GET READY (BUY)"
                    icon = "⚠️"
                    alert_msg = f"{icon} {signal} - {symbol}\nPrice is ${live_price - live_ema:.2f} away from EMA!\nEMA: {live_ema:.2f}\nTime: {now}"
                    self.alerted_events.add(alert_id)

        # ================= SELL LOGIC =================
        elif dist_dn >= MIN_TRAVEL_PRICE:
            # 1. EXECUTION CHECK (Did the closed candle touch and reject below 200 EMA?)
            if last_closed['high'] >= last_closed['ema_200'] and last_closed['close'] < last_closed['ema_200']:
                if df.iloc[-3]['close'] < df.iloc[-3]['ema_200']: # Anti-breakout filter
                    sl, tp, risk_pts, rr, lot = self.calc_trade_intelligence(entry_price, "DOWN")
                    
                    # Risk-to-Reward Smart Filter
                    if rr >= MIN_RR_RATIO:
                        alert_id = f"{candle_time}_sell_exec"
                        if alert_id not in self.alerted_events:
                            signal = "SELL EXECUTING"
                            icon = "🔴"
                            alert_msg = f"{icon} {signal} - {symbol}\nEntry @ {entry_price:.2f}\nSL: {sl:.2f} | TP: {tp:.2f}\nLot: {lot} ($100 Risk)\nRR: 1:{rr:.1f}\nTime: {now}"
                            self.alerted_events.add(alert_id)
                    else:
                        print(f"{now} | Skipped Invalid SELL Setup at {entry_price:.2f} due to poor RR (1:{rr:.1f})")
                        
            # 2. PRE-ALERT CHECK
            elif live_price < live_ema and (live_ema - live_price) <= PRE_ALERT_BUFFER:
                alert_id = f"{candle_time}_sell_ready"
                if alert_id not in self.alerted_events:
                    signal = "GET READY (SELL)"
                    icon = "⚠️"
                    alert_msg = f"{icon} {signal} - {symbol}\nPrice is ${live_ema - live_price:.2f} away from EMA!\nEMA: {live_ema:.2f}\nTime: {now}"
                    self.alerted_events.add(alert_id)

        print(f"{now} | {symbol: <6} | C: {live_price:.2f} | EMA: {live_ema:.2f} | UP: {dist_up:.2f} | DN: {dist_dn:.2f} | {signal if signal else 'Waiting...'}")

        if signal:
            self.send_telegram(alert_msg)
            print(f"   >>> TELEGRAM ALERT SENT: {signal} <<<")

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
        if time.time() - self.last_fetch > 14400:
            try:
                resp = requests.get(self.url)
                self.news_data = [n for n in resp.json() if n.get("country") in self.target_currencies and n.get("impact") == "High"]
                self.last_fetch = time.time()
                print(">>> News Data Updated from API <<<")
            except Exception as e:
                pass

    def run(self):
        self.fetch_news()
        now = datetime.now(pytz.utc)

        for news in self.news_data:
            try:
                news_time = datetime.fromisoformat(news["date"]).astimezone(pytz.utc)
            except: continue
            
            time_diff_mins = (news_time - now).total_seconds() / 60.0
            news_id = f"{news['title']}_{news['date']}"
            
            if 0 < time_diff_mins <= 30 and f"{news_id}_before" not in self.alerted:
                msg = f"🚨 RED FOLDER NEWS ALERT 🚨\n\nCurrency: {news['country']}\nEvent: {news['title']}\nTime Left: {int(time_diff_mins)} Mins Before"
                self.send_telegram(msg)
                self.alerted.add(f"{news_id}_before")
            
            elif -15 <= time_diff_mins < 0 and f"{news_id}_after" not in self.alerted:
                msg = f"✅ VOLATILITY SETTLED ✅\n\nCurrency: {news['country']}\nEvent: {news['title']}\nStatus: 15 Mins Passed"
                self.send_telegram(msg)
                self.alerted.add(f"{news_id}_after")

# =============== ORCHESTRATOR =================
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        self.data_agent = DataAgent(timeframe=mt5.TIMEFRAME_M1, limit=500) 
        self.ema_agent = EMAAgent()
        self.alert_agent = AlertAgent(BOT_TOKEN, CHAT_ID)
        self.news_agent = NewsAgent(BOT_TOKEN, CHAT_ID)
        self.active_symbols = TARGET_SYMBOLS

    def run(self):
        self.news_agent.run()
        for symbol in self.active_symbols:
            self.data_agent.symbol = symbol
            df = self.data_agent.run()
            df = self.ema_agent.run(df)
            self.alert_agent.run(df, symbol)
            time.sleep(0.1) 

# =============== MAIN =================
if __name__ == "__main__":
    if not mt5.initialize():
        print(f"MT5 initialization failed. Error: {mt5.last_error()}")
        quit()

    bot = OrchestratorAgent()
    print(f"Bot Starting for {TARGET_SYMBOLS} on 1m Timeframe via MT5...")
    print(f"Active Parameters: Minimum Distance = ${MIN_TRAVEL_PRICE}, Pre-Alert Buffer = ${PRE_ALERT_BUFFER}\n")
    
    try:
        while True:
            bot.run()
            time.sleep(LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\nBot Stopped by User.")
    finally:
        mt5.shutdown()
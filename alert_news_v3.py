import MetaTrader5 as mt5
import requests
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from datetime import datetime, timezone
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"

TARGET_SYMBOLS = ["XAUUSD"]
TIMEFRAME = mt5.TIMEFRAME_M1
LOOP_SLEEP_SECONDS = 5

# Strategy & Alert Limits
MAX_PATTERN_CANDLES = 90
SL_BUFFER = 0.50
RR_MULTIPLIER = 1.0
MAX_ALERTS_PER_ENTRY = 5   # 🔥 Har entry ke liye exact 5 alerts

# =============== TELEGRAM SENDER =================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

# =============== DATA FETCH AGENT =================
class DataAgent:
    def __init__(self, timeframe=TIMEFRAME, limit=1000):
        self.timeframe = timeframe
        self.limit = limit

    def run(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, self.limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')
        
        df['EMA_285'] = ta.ema(df['close'], length=285)
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3.0
        df['RSI'] = ta.rsi(df['hlc3'], length=14)
        
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

# =============== SMC SWEEP & BOS SIGNAL AGENT =================
class SMCSignalAgent:
    def __init__(self):
        self.entry_alert_tracker = {}
        self.last_tracker_print = ""

    def scan(self, df: pd.DataFrame, symbol: str):
        if len(df) < MAX_PATTERN_CANDLES + 20:
            return None

        # 🔥 THE FIX: Sirf CLOSED candles ko read karenge
        df_closed = df.iloc[:-1].reset_index(drop=True)
        
        time_arr = df_closed['time'].to_numpy()
        open_p = df_closed['open'].to_numpy()
        high_p = df_closed['high'].to_numpy()
        low_p = df_closed['low'].to_numpy()
        close_p = df_closed['close'].to_numpy()
        ema_285 = df_closed['EMA_285'].to_numpy()
        rsi_p = df_closed['RSI'].to_numpy()

        i = len(df_closed) - 1
        c_open, c_high, c_low, c_close, c_ema = open_p[i], high_p[i], low_p[i], close_p[i], ema_285[i]
        
        candle_ts = pd.Timestamp(time_arr[i])
        candle_time = candle_ts.strftime("%Y-%m-%d %H:%M")

        time_hm = candle_ts.hour * 100 + candle_ts.minute
        if time_hm < 1130:
            return None

        # 📈 BUY SETUP (Live Bot logic match: EMA check & Green Candle)
        if c_close > c_ema and c_close > c_open:
            start_c = max(0, i - MAX_PATTERN_CANDLES)
            recent_lows = low_p[start_c : i]
            c_idx = start_c + np.argmin(recent_lows)
            c_low_val = recent_lows.min()

            if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                start_b = max(0, c_idx - 15)
                if start_b < c_idx:
                    recent_highs = high_p[start_b : c_idx]
                    b_idx = start_b + np.argmax(recent_highs)
                    b_high_val = recent_highs.max()

                    start_a = max(0, b_idx - 15)
                    if start_a < b_idx:
                        initial_lows = low_p[start_a : b_idx]
                        a_idx = start_a + np.argmin(initial_lows)
                        a_low_val = initial_lows.min()

                        if c_low_val < a_low_val:
                            rsi_near_a = np.min(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                            
                            tracker_msg = f"👀 [BUY TRACKER] Point A: {a_low_val:.2f} (RSI: {rsi_near_a:.2f}) | Point B (BOS): {b_high_val:.2f} | Sweep C: {c_low_val:.2f} | Waiting..."
                            if tracker_msg != self.last_tracker_print:
                                print(f"\n{tracker_msg}")
                                self.last_tracker_print = tracker_msg

                            if rsi_near_a < 30.0:
                                if c_close > b_high_val:
                                    closes_since_c = close_p[c_idx+1 : i]
                                    if not np.any(closes_since_c > b_high_val):
                                        setup_id = f"{symbol}_BUY_{candle_time}"
                                        count = self.entry_alert_tracker.get(setup_id, 0)

                                        if count < MAX_ALERTS_PER_ENTRY:
                                            self.entry_alert_tracker[setup_id] = count + 1
                                            sl_distance = max(0.50, c_close - (c_low_val - SL_BUFFER))
                                            sl_price = c_close - sl_distance
                                            tp_price = c_close + (RR_MULTIPLIER * sl_distance)

                                            return {
                                                "direction": "BUY",
                                                "entry": c_close,
                                                "sl": sl_price,
                                                "tp": tp_price,
                                                "rsi": rsi_p[i],
                                                "ema": c_ema,
                                                "time": candle_time,
                                                "alert_num": count + 1
                                            }

        # 📉 SELL SETUP (Live Bot logic match: EMA check & Red Candle)
        elif c_close < c_ema and c_close < c_open:
            start_c = max(0, i - MAX_PATTERN_CANDLES)
            recent_highs = high_p[start_c : i]
            c_idx = start_c + np.argmax(recent_highs)
            c_high_val = recent_highs.max()

            if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                start_b = max(0, c_idx - 15)
                if start_b < c_idx:
                    recent_lows = low_p[start_b : c_idx]
                    b_idx = start_b + np.argmin(recent_lows)
                    b_low_val = recent_lows.min()

                    start_a = max(0, b_idx - 15)
                    if start_a < b_idx:
                        initial_highs = high_p[start_a : b_idx]
                        a_idx = start_a + np.argmax(initial_highs)
                        a_high_val = initial_highs.max()

                        if c_high_val > a_high_val:
                            rsi_near_a = np.max(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                            
                            tracker_msg = f"👀 [SELL TRACKER] Point A: {a_high_val:.2f} (RSI: {rsi_near_a:.2f}) | Point B (BOS): {b_low_val:.2f} | Sweep C: {c_high_val:.2f} | Waiting..."
                            if tracker_msg != self.last_tracker_print:
                                print(f"\n{tracker_msg}")
                                self.last_tracker_print = tracker_msg

                            if rsi_near_a > 70.0:
                                if c_close < b_low_val:
                                    closes_since_c = close_p[c_idx+1 : i]
                                    if not np.any(closes_since_c < b_low_val):
                                        setup_id = f"{symbol}_SELL_{candle_time}"
                                        count = self.entry_alert_tracker.get(setup_id, 0)

                                        if count < MAX_ALERTS_PER_ENTRY:
                                            self.entry_alert_tracker[setup_id] = count + 1
                                            sl_distance = max(0.50, (c_high_val + SL_BUFFER) - c_close)
                                            sl_price = c_close + sl_distance
                                            tp_price = c_close - (RR_MULTIPLIER * sl_distance)

                                            return {
                                                "direction": "SELL",
                                                "entry": c_close,
                                                "sl": sl_price,
                                                "tp": tp_price,
                                                "rsi": rsi_p[i],
                                                "ema": c_ema,
                                                "time": candle_time,
                                                "alert_num": count + 1
                                            }
        return None

# =============== ORCHESTRATOR =================
class Orchestrator:
    def __init__(self):
        self.data_agent = DataAgent()
        self.signal_agent = SMCSignalAgent()

    def run(self):
        ist_now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p")
        print(f"\r[{ist_now}] Scanning pairs... (100% Match with Live Bot) | XAUUSD Price Check", end="")

        for symbol in TARGET_SYMBOLS:
            df = self.data_agent.run(symbol)
            if df.empty:
                continue

            signal = self.signal_agent.scan(df, symbol)
            if signal:
                icon = "🟢 BUY" if signal["direction"] == "BUY" else "🔴 SELL"
                msg = (f"🎯 *SMC SWEEP + BOS ALERT ({signal['alert_num']}/{MAX_ALERTS_PER_ENTRY})* 🎯\n\n"
                       f"Pair: *{symbol}*\n"
                       f"Direction: *{icon}*\n"
                       f"Entry: `{signal['entry']:.2f}`\n"
                       f"Stop Loss: `{signal['sl']:.2f}`\n"
                       f"Take Profit: `{signal['tp']:.2f}`\n"
                       f"Risk/Reward: *1:1*\n"
                       f"285 EMA: `{signal['ema']:.2f}`\n"
                       f"Time (IST): `{signal['time']}`")
                send_telegram(msg)
                print(f"\n 🔥 ALERT {signal['alert_num']}/{MAX_ALERTS_PER_ENTRY} SENT FOR {symbol} ({signal['direction']}) 🔥 \n")

# =============== MAIN LOOP =================
if __name__ == "__main__":
    if not mt5.initialize():
        print(f"MT5 Initialization failed: {mt5.last_error()}")
        quit()

    bot = Orchestrator()
    print(f"🚀 SMC Alert Bot (Max {MAX_ALERTS_PER_ENTRY} Alerts per Entry) Running on {TARGET_SYMBOLS}...")
    print("📡 Waiting for market setups (News Block REMOVED for 100% sync)...\n")

    try:
        while True:
            bot.run()
            time.sleep(LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    finally:
        mt5.shutdown()
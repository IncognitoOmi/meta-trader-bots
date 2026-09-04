import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import math
from datetime import datetime, timedelta, timezone

# ============================================================
# ⚙️ 1. CONFIGURATION & SETTINGS
# ============================================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M15  
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"
mt5_terminal_path = r"C:\Program Files\MetaTrader 5 - FP_master\terminal64.exe"

STARTING_CAPITAL = 5000.0
RISK_PER_TRADE = 30.0          

# Strategy Parameters
ATR_MULTIPLIER = 3.0           # Tightened to 3x ATR for faster hit rate
MAX_PIVOT_DISTANCE = 50        
MIN_PIVOT_DISTANCE = 5         

if not mt5.initialize(path=mt5_terminal_path):
    raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

if not mt5.login(login=account_login, password=account_password, server=broker_server):
    mt5.shutdown()
    raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")

# ============================================================
# 📊 2. FETCH DATA & INDICATORS
# ============================================================
print(f"📥 Fetching 365 Days {symbol} Data & Calculating Indicators...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365)

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    mt5.shutdown()
    raise RuntimeError("No data fetched.")

df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")

# Indicators
df["EMA_285"] = ta.ema(df["close"], length=285)
df["RSI"] = ta.rsi(df["close"], length=14)
df["ATR"] = ta.atr(high=df["high"], low=df["low"], close=df["close"], length=14)

# Manual Bollinger Bands (Stable cross-version)
df["SMA_20"] = df["close"].rolling(20).mean()
df["STD_20"] = df["close"].rolling(20).std()
df["BBU"] = df["SMA_20"] + (2.0 * df["STD_20"])
df["BBL"] = df["SMA_20"] - (2.0 * df["STD_20"])

df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

time_arr = df["time"].to_numpy()
open_p = df["open"].to_numpy(dtype=float)
high_p = df["high"].to_numpy(dtype=float)
low_p = df["low"].to_numpy(dtype=float)
close_p = df["close"].to_numpy(dtype=float)

ema_285 = df["EMA_285"].to_numpy(dtype=float)
rsi_p = df["RSI"].to_numpy(dtype=float)
atr_p = df["ATR"].to_numpy(dtype=float)
bbu_p = df["BBU"].to_numpy(dtype=float)
bbl_p = df["BBL"].to_numpy(dtype=float)

total_candles = len(close_p)

# ============================================================
# 🧠 3. STATE CONTROLS
# ============================================================
tp_hits, sl_hits = 0, 0
running_capital = STARTING_CAPITAL
account_blown = False

active_trade = False
direction = ""
entry_price = tp = sl = current_lot = 0.0
entry_time_str = ""

def get_dynamic_lot(sl_distance_points, risk_amount):
    if sl_distance_points <= 0: return 0.01
    calculated_lot = risk_amount / (sl_distance_points * 100.0)
    final_lot = math.floor(calculated_lot * 100.0) / 100.0
    return max(0.01, min(final_lot, 50.0))

print("\n" + "="*120)
print(f"{'ENTRY TIME (IST)':<19} | {'DIR':<4} | {'ENTRY':<8} | {'SL':<8} | {'TP':<8} | {'LOT':<4} | {'RES':<6} | {'PNL':<9} | {'BALANCE'}")
print("="*120)

# Pivot Tracking
last_pivot_low_idx = -1
last_pivot_low_price = 0.0
last_pivot_low_rsi = 0.0

last_pivot_high_idx = -1
last_pivot_high_price = 0.0
last_pivot_high_rsi = 0.0

# ============================================================
# 🔄 4. ZERO-LOOKAHEAD EXECUTION LOOP
# ============================================================
for i in range(10, total_candles - 1):
    
    # --------------------------------------------------------
    # 1. TRADE MANAGEMENT
    # --------------------------------------------------------
    if active_trade:
        trade_closed = False
        pnl = 0.0
        result = ""

        if direction == "BUY":
            if low_p[i] <= sl and high_p[i] >= tp:
                sl_hits += 1; pnl = -RISK_PER_TRADE; result = "LOSS"; trade_closed = True
            elif low_p[i] <= sl:
                sl_hits += 1; pnl = -RISK_PER_TRADE; result = "LOSS"; trade_closed = True
            elif high_p[i] >= tp:
                tp_hits += 1; pnl = RISK_PER_TRADE; result = "WIN"; trade_closed = True

        elif direction == "SELL":
            if high_p[i] >= sl and low_p[i] <= tp:
                sl_hits += 1; pnl = -RISK_PER_TRADE; result = "LOSS"; trade_closed = True
            elif high_p[i] >= sl:
                sl_hits += 1; pnl = -RISK_PER_TRADE; result = "LOSS"; trade_closed = True
            elif low_p[i] <= tp:
                tp_hits += 1; pnl = RISK_PER_TRADE; result = "WIN"; trade_closed = True

        if trade_closed:
            active_trade = False
            running_capital += pnl
            print(f"{entry_time_str:<19} | {direction:<4} | {entry_price:<8.2f} | {sl:<8.2f} | {tp:<8.2f} | {current_lot:<4.2f} | {result:<6} | {'+$' if pnl>=0 else '-$'}{abs(pnl):<8.2f} | ${running_capital:.2f}")

            if running_capital < (STARTING_CAPITAL * 0.90): 
                account_blown = True
                break

    # --------------------------------------------------------
    # 2. RSI + BOLLINGER EXHAUSTION SCANNER
    # --------------------------------------------------------
    if not active_trade and not account_blown:
        c_close = close_p[i]
        c_ema = ema_285[i]
        c_atr = atr_p[i]

        # FRACTAL DETECTION
        is_pivot_low = (low_p[i-2] < low_p[i-3] and low_p[i-2] < low_p[i-4] and 
                        low_p[i-2] <= low_p[i-1] and low_p[i-2] <= low_p[i])
        
        is_pivot_high = (high_p[i-2] > high_p[i-3] and high_p[i-2] > high_p[i-4] and 
                         high_p[i-2] >= high_p[i-1] and high_p[i-2] >= high_p[i])

        # 🟢 BULLISH DIVERGENCE + BB EXHAUSTION
        if is_pivot_low:
            curr_pivot_low_price = low_p[i-2]
            curr_pivot_low_rsi = rsi_p[i-2]
            curr_bbl = bbl_p[i-2]
            
            if last_pivot_low_idx != -1:
                dist = (i - 2) - last_pivot_low_idx
                if MIN_PIVOT_DISTANCE <= dist <= MAX_PIVOT_DISTANCE:
                    
                    # CONDITIONS: Lower Low, Higher RSI, Above EMA, PIERCED LOWER BBAND
                    if (curr_pivot_low_price < last_pivot_low_price and 
                        curr_pivot_low_rsi > last_pivot_low_rsi and 
                        curr_pivot_low_price <= curr_bbl and   # 🔥 BB Exhaustion
                        c_close > c_ema):
                        
                        active_trade = True
                        direction = "BUY"
                        entry_price = open_p[i+1] 
                        
                        atr_distance = c_atr * ATR_MULTIPLIER
                        sl = entry_price - atr_distance
                        tp = entry_price + atr_distance
                        
                        current_lot = get_dynamic_lot(atr_distance, RISK_PER_TRADE)
                        entry_time_str = pd.Timestamp(time_arr[i+1]).strftime("%Y-%m-%d %H:%M")

            last_pivot_low_idx = i - 2
            last_pivot_low_price = curr_pivot_low_price
            last_pivot_low_rsi = curr_pivot_low_rsi

        # 🔴 BEARISH DIVERGENCE + BB EXHAUSTION
        elif is_pivot_high:
            curr_pivot_high_price = high_p[i-2]
            curr_pivot_high_rsi = rsi_p[i-2]
            curr_bbu = bbu_p[i-2]
            
            if last_pivot_high_idx != -1:
                dist = (i - 2) - last_pivot_high_idx
                if MIN_PIVOT_DISTANCE <= dist <= MAX_PIVOT_DISTANCE:
                    
                    # CONDITIONS: Higher High, Lower RSI, Below EMA, PIERCED UPPER BBAND
                    if (curr_pivot_high_price > last_pivot_high_price and 
                        curr_pivot_high_rsi < last_pivot_high_rsi and 
                        curr_pivot_high_price >= curr_bbu and  # 🔥 BB Exhaustion
                        c_close < c_ema):
                        
                        active_trade = True
                        direction = "SELL"
                        entry_price = open_p[i+1] 
                        
                        atr_distance = c_atr * ATR_MULTIPLIER
                        sl = entry_price + atr_distance
                        tp = entry_price - atr_distance
                        
                        current_lot = get_dynamic_lot(atr_distance, RISK_PER_TRADE)
                        entry_time_str = pd.Timestamp(time_arr[i+1]).strftime("%Y-%m-%d %H:%M")

            last_pivot_high_idx = i - 2
            last_pivot_high_price = curr_pivot_high_price
            last_pivot_high_rsi = curr_pivot_high_rsi

print("=" * 120)
print("📊 SIMULATION SUMMARY (RSI DIV + BOLLINGER BANDS | 3x ATR)")
print("=" * 120)

if account_blown:
    print(f"💀 ACCOUNT BLOWN")
else:
    print("🏆 ACCOUNT SURVIVED!")

print(f"🏦 Final Balance : ${running_capital:.2f}")
print(f"✅ Total Wins    : {tp_hits}")
print(f"❌ Total Losses  : {sl_hits}")

closed_trades = tp_hits + sl_hits
win_rate = (tp_hits / closed_trades * 100.0) if closed_trades > 0 else 0.0
print(f"🎯 Win Rate      : {win_rate:.2f}%")
print("=" * 120)

mt5.shutdown()
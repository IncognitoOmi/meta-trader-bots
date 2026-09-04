import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import math
from datetime import datetime, timedelta, timezone
import pytz

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 720887034 
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"

STARTING_CAPITAL = 5000  

# 🚨 1-STEP EVALUATION RULES 🚨
IS_EVALUATION = False          # Set to False to skip straight to Master
EVAL_PROFIT_TARGET = 0.10     # 10% Profit Target ($2500)
EVAL_DAILY_DD = 0.03          # 3% Daily Drawdown ($750)
EVAL_TRAILING_DD = 0.05       # 6% Trailing Drawdown ($1500)

# 🚨 MASTER (FUNDED) PROP FIRM RULES 🚨
MASTER_PAYOUT_TARGET = 5500
MASTER_PAYOUT_AMOUNT = 100
MASTER_MIN_PAYOUT_DAYS = 14
MASTER_DAILY_DD_LIMIT = 150         
MASTER_INITIAL_OVERALL_FLOOR = STARTING_CAPITAL * (1 - EVAL_TRAILING_DD) # $23500 initially
MASTER_TRAPDOOR_FLOOR = 5000.0      # Locks at $25k permanently

# STRATEGY RISK RULES
INITIAL_MAX_RISK = 30.0            # Pre-Payout Risk per trade
POST_PAYOUT_MAX_RISK = 40.0         # Post-Payout Risk per trade

# 🔥 SMC SETTINGS
SL_BUFFER = 0.50       # $0.50 (5 pips) below sweep wick
RR_MULTIPLIER = 1.0    # 1:1 Risk Reward
MAX_PATTERN_CANDLES = 45 # Window limit for the sweep setup to unfold

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA (365 DAYS)
# ==========================================
print("📥 Fetching historical data (Wait...).")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365) # 365 Days setup

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)

# 🕒 TIMEZONE FIX
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

print("⚙️ Calculating Indicators...")
df['EMA_285'] = ta.ema(df['close'], length=285)

# Calculate HLC3 (Typical Price) for RSI
df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3.0
df['RSI'] = ta.rsi(df['hlc3'], length=14)

df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# 🔥 NUMPY CONVERSION FOR EXTREME SPEED 🔥
print("🚀 Compiling arrays for speed...")
time_arr = df['time'].to_numpy()
date_arr = df['time'].dt.date.to_numpy()
time_hm_arr = (df['time'].dt.hour * 100 + df['time'].dt.minute).to_numpy()

open_p = df['open'].to_numpy()
high_p = df['high'].to_numpy()
low_p = df['low'].to_numpy()
close_p = df['close'].to_numpy()
ema_285 = df['EMA_285'].to_numpy()
rsi_p = df['RSI'].to_numpy()

total_candles = len(close_p)

# ==========================================
# 🧠 3. STRATEGY ENGINE & PROP FIRM TRACKER
# ==========================================
tp_hits, sl_hits = 0, 0
running_capital = STARTING_CAPITAL
is_eval_active = IS_EVALUATION

# State Variables
current_day = None
start_of_day_balance = STARTING_CAPITAL
unique_trading_days = set()
total_payouts_extracted = 0.0
payout_count = 0
account_blown = False
blown_reason = ""

# Eval specific tracking
high_watermark = STARTING_CAPITAL
eval_trailing_floor = STARTING_CAPITAL * (1 - EVAL_TRAILING_DD)

# Master specific tracking
daily_floor = start_of_day_balance - MASTER_DAILY_DD_LIMIT
overall_floor = MASTER_INITIAL_OVERALL_FLOOR

# Dynamic Risk Variables
current_max_risk = INITIAL_MAX_RISK

# Single Trade Variables
active_trade = False
direction = ""
entry_price = tp = sl = current_lot = 0
entry_time_str = ""

def get_dynamic_lot(sl_distance, active_max_risk):
    if sl_distance <= 0: return 0.01
    calculated_lot = active_max_risk / (sl_distance * 100.0)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    return max(0.01, min(final_lot, 50.0))

def calc_exact_pnl(dir, exit_p, e_p, lot):
    contract = 100.0
    if dir == "BUY":
        return (exit_p - e_p) * lot * contract
    else:
        return (e_p - exit_p) * lot * contract

print("\n" + "="*140)
print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
print("="*140)

# 🔥 FAST LOOP OVER NUMPY ARRAYS 🔥
for i in range(MAX_PATTERN_CANDLES + 20, total_candles):
    
    curr_date = date_arr[i]
    time_hm = time_hm_arr[i]
    
    c_open = open_p[i]
    c_high = high_p[i]
    c_low = low_p[i]
    c_close = close_p[i]
    c_ema = ema_285[i]
    
    # 🗓️ DAILY DRAWDOWN RESET LOGIC
    if curr_date != current_day:
        current_day = curr_date
        start_of_day_balance = running_capital
        if is_eval_active:
            daily_floor = start_of_day_balance - (STARTING_CAPITAL * EVAL_DAILY_DD)
        else:
            daily_floor = start_of_day_balance - MASTER_DAILY_DD_LIMIT
            
    if active_trade:
        trade_closed = False
        exit_time_str_val = pd.Timestamp(time_arr[i]).strftime('%Y-%m-%d %H:%M')

        if direction == "BUY":
            if c_low <= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("BUY", sl, entry_price, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_price:<8.2f} | {exit_time_str_val:<19} | {sl:<8.2f} | {current_lot:<4.2f} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
            elif c_high >= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("BUY", tp, entry_price, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_price:<8.2f} | {exit_time_str_val:<19} | {tp:<8.2f} | {current_lot:<4.2f} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
        elif direction == "SELL":
            if c_high >= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("SELL", sl, entry_price, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_price:<8.2f} | {exit_time_str_val:<19} | {sl:<8.2f} | {current_lot:<4.2f} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
            elif c_low <= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("SELL", tp, entry_price, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_price:<8.2f} | {exit_time_str_val:<19} | {tp:<8.2f} | {current_lot:<4.2f} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                trade_closed = True

        # 🚨 PROP FIRM ACCOUNT CHECKS AFTER TRADE CLOSES
        if trade_closed:
            active_trade = False
            unique_trading_days.add(curr_date)
            
            # 🔥 UPDATE HIGH WATERMARK & LOCKING TRAILING DD
            if running_capital > high_watermark:
                high_watermark = running_capital
                if is_eval_active:
                    new_floor = high_watermark - (STARTING_CAPITAL * EVAL_TRAILING_DD)
                    eval_trailing_floor = max(eval_trailing_floor, min(STARTING_CAPITAL, new_floor))
                else:
                    if payout_count == 0:
                        new_floor = high_watermark - (STARTING_CAPITAL * EVAL_TRAILING_DD)
                        overall_floor = max(overall_floor, min(STARTING_CAPITAL, new_floor))

            if is_eval_active:
                if running_capital < daily_floor:
                    account_blown = True
                    blown_reason = f"EVAL FAILED: Daily DD Reached! Dropped below ${daily_floor:.2f}"
                    break
                if running_capital < eval_trailing_floor:
                    account_blown = True
                    blown_reason = f"EVAL FAILED: Trailing DD Reached! Dropped below ${eval_trailing_floor:.2f}"
                    break
                
                if running_capital >= STARTING_CAPITAL * (1 + EVAL_PROFIT_TARGET):
                    print("-" * 140)
                    print(f"🎉 1-STEP EVALUATION PASSED! Balance reached: ${running_capital:.2f}")
                    print("🚀 MIGRATING TO MASTER (FUNDED) ACCOUNT...")
                    print("-" * 140)
                    is_eval_active = False
                    running_capital = STARTING_CAPITAL
                    start_of_day_balance = STARTING_CAPITAL
                    daily_floor = start_of_day_balance - MASTER_DAILY_DD_LIMIT
                    
                    high_watermark = STARTING_CAPITAL
                    overall_floor = STARTING_CAPITAL * (1 - EVAL_TRAILING_DD)
                    unique_trading_days.clear()

            else:
                if running_capital < daily_floor:
                    account_blown = True
                    blown_reason = f"MASTER BLOWN: Daily Drawdown Reached! Dropped below ${daily_floor:.2f}"
                    break
                
                if running_capital < overall_floor:
                    account_blown = True
                    blown_reason = f"MASTER BLOWN: Overall Drawdown Reached! Dropped below ${overall_floor:.2f}"
                    break
                
                # 🔥 PAYOUT LOGIC 🔥
                if running_capital >= MASTER_PAYOUT_TARGET and len(unique_trading_days) >= MASTER_MIN_PAYOUT_DAYS:
                    print("-" * 140)
                    print(f"🎉 PAYOUT UNLOCKED! Target: ${MASTER_PAYOUT_TARGET} | Trading Days: {len(unique_trading_days)}")
                    print(f"💸 Extracting Payout: ${MASTER_PAYOUT_AMOUNT}")
                    
                    running_capital -= MASTER_PAYOUT_AMOUNT
                    total_payouts_extracted += MASTER_PAYOUT_AMOUNT
                    payout_count += 1
                    
                    if payout_count == 1:
                        overall_floor = MASTER_TRAPDOOR_FLOOR 
                        current_max_risk = POST_PAYOUT_MAX_RISK
                        print(f"🛡️ Trapdoor Activated! Overall Floor locked at: ${overall_floor:.2f}")
                    
                    unique_trading_days.clear()
                    start_of_day_balance = running_capital 
                    daily_floor = start_of_day_balance - MASTER_DAILY_DD_LIMIT
                    print(f"🏦 Account Balance after Payout: ${running_capital:.2f}")
                    print("-" * 140)

    else:
        # STRATEGY ENTRY LOGIC (SMC LIQUIDITY SWEEP + BOS) - VECTORIZED
        if time_hm >= 1130:
            
            # 📈 BUY LOGIC (Trend is UP)
            if c_close > c_ema and c_close > c_open:
                
                start_c = max(0, i - MAX_PATTERN_CANDLES)
                recent_lows = low_p[start_c : i]
                c_idx = start_c + np.argmin(recent_lows)
                c_low = recent_lows.min()
                
                if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                    
                    start_b = max(0, c_idx - 15)
                    if start_b < c_idx:
                        recent_highs = high_p[start_b : c_idx]
                        b_idx = start_b + np.argmax(recent_highs)
                        b_high = recent_highs.max()
                        
                        start_a = max(0, b_idx - 15)
                        if start_a < b_idx:
                            initial_lows = low_p[start_a : b_idx]
                            a_idx = start_a + np.argmin(initial_lows)
                            a_low = initial_lows.min()
                            
                            if c_low < a_low:
                                rsi_near_a = np.min(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                                
                                if rsi_near_a < 30.0:
                                    if c_close > b_high:
                                        closes_since_c = close_p[c_idx+1 : i]
                                        if not np.any(closes_since_c > b_high):
                                            
                                            # ✅ EXECUTE BUY
                                            active_trade = True
                                            direction = "BUY"
                                            
                                            entry_price = c_open 
                                            entry_time_str = pd.Timestamp(time_arr[i]).strftime('%Y-%m-%d %H:%M')
                                            
                                            sl = c_low - SL_BUFFER
                                            sl_distance = entry_price - sl
                                            
                                            if sl_distance < 0.50: sl_distance = 0.50
                                            sl = entry_price - sl_distance
                                            
                                            tp = entry_price + sl_distance
                                            current_lot = get_dynamic_lot(sl_distance, current_max_risk)
                                            
            # 📉 SELL LOGIC (Trend is DOWN)
            elif c_close < c_ema and c_close < c_open:
                
                start_c = max(0, i - MAX_PATTERN_CANDLES)
                recent_highs = high_p[start_c : i]
                c_idx = start_c + np.argmax(recent_highs)
                c_high = recent_highs.max()
                
                if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                    
                    start_b = max(0, c_idx - 15)
                    if start_b < c_idx:
                        recent_lows = low_p[start_b : c_idx]
                        b_idx = start_b + np.argmin(recent_lows)
                        b_low = recent_lows.min()
                        
                        start_a = max(0, b_idx - 15)
                        if start_a < b_idx:
                            initial_highs = high_p[start_a : b_idx]
                            a_idx = start_a + np.argmax(initial_highs)
                            a_high = initial_highs.max()
                            
                            if c_high > a_high:
                                rsi_near_a = np.max(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                                
                                if rsi_near_a > 70.0:
                                    if c_close < b_low:
                                        closes_since_c = close_p[c_idx+1 : i]
                                        if not np.any(closes_since_c < b_low):
                                            
                                            # ✅ EXECUTE SELL
                                            active_trade = True
                                            direction = "SELL"
                                            
                                            entry_price = c_open
                                            entry_time_str = pd.Timestamp(time_arr[i]).strftime('%Y-%m-%d %H:%M')
                                            
                                            sl = c_high + SL_BUFFER
                                            sl_distance = sl - entry_price
                                            
                                            if sl_distance < 0.50: sl_distance = 0.50
                                            sl = entry_price + sl_distance
                                            
                                            tp = entry_price - sl_distance
                                            current_lot = get_dynamic_lot(sl_distance, current_max_risk)

print("="*140)
print(f"📊 PROP FIRM SIMULATION SUMMARY (SMC SWEEP + BOS | 1:1 RR | FAST NUMPY)")
print("="*140)

if account_blown:
    print(f"💀 ACCOUNT BLOWN! 💀")
    print(f"📉 Reason: {blown_reason}")
    print(f"🏦 Final Balance before blowing: ${running_capital:.2f}")
else:
    print(f"🏆 ACCOUNT SURVIVED! 🏆")
    print(f"🏦 Final Prop Balance: ${running_capital:.2f}")

print("-" * 40)
print(f"✅ Total Wins   : {tp_hits}")
print(f"❌ Total Losses : {sl_hits}")
win_rate = (tp_hits/(tp_hits+sl_hits))*100 if (tp_hits+sl_hits) > 0 else 0
print(f"🎯 Win Rate     : {win_rate:.2f}%")
print("-" * 40)
print(f"💸 Total Payouts Reached : {payout_count}")
print(f"💰 Total Money Extracted : ${total_payouts_extracted:.2f}")
print("="*140)

mt5.shutdown()
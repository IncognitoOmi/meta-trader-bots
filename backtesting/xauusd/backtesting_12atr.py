import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
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

STARTING_CAPITAL = 5000.0  
MAX_RISK = 200.0  # Tera Max Risk yahan set hai
MIN_SAFE_ATR = 1.5  

# 🚨 DYNAMIC GRID SETTINGS
MAX_LAYERS = 5  
SL_ATR_MULT = MAX_LAYERS * 2  
RISK_MULT = sum(range(2, SL_ATR_MULT + 1, 2))  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA
# ==========================================
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=69) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)

# 🕒 TIMEZONE FIX: Localize to EET (Europe/Athens) and convert to IST (Asia/Kolkata)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df['EMA_200'] = ta.ema(df['close'], length=100)
df['RSI'] = ta.rsi(df['close'], length=14)
df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# ==========================================
# 🧠 3. STRATEGY ENGINE & DYNAMIC PNL
# ==========================================
tp_hits, sl_hits = 0, 0
total_pnl = 0.0 
running_capital = STARTING_CAPITAL

active_trade = False
direction = ""
entry_price = tp = sl = current_lot = entry_rsi = entry_atr = 0
orders_open = 0 
entry_time = None
layers_prices = []

def get_fixed_atr(raw_atr):
    adj = raw_atr - 0.5
    if adj < MIN_SAFE_ATR:
        return MIN_SAFE_ATR
    return round(adj, 2)

# 🚨 Tera naya Dynamic Lot Logic
def get_dynamic_lot(fixed_atr):
    calculated_lot = MAX_RISK / (42 * fixed_atr * 100.0)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    return max(0.01, min(final_lot, 10.0))

def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
    pnl = 0.0
    contract = 100.0
    if dir == "BUY":
        pnl += (exit_p - e_p) * lot * contract
        for i in range(total_orders - 1):
            pnl += (exit_p - l_prices[i]) * lot * contract
    else:
        pnl += (e_p - exit_p) * lot * contract
        for i in range(total_orders - 1):
            pnl += (l_prices[i] - exit_p) * lot * contract
    return pnl

print("\n" + "="*150)
print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
print("="*150)

for i in range(1, len(df)):
    curr = df.iloc[i]
    prev = df.iloc[i-1]
    
    # 🕒 Direct IST time from localized dataframe
    curr_ist_time = curr['time']
    time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
    
    if active_trade:
        exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
        entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')

        if direction == "BUY":
            while orders_open < 6 and curr['low'] <= layers_prices[orders_open - 1]:
                orders_open += 1
                
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                    tp = round(avg_entry, 2)
                    
            if curr['low'] <= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                active_trade = False
                continue
                
            elif curr['high'] >= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                active_trade = False
                
        elif direction == "SELL":
            while orders_open < 6 and curr['high'] >= layers_prices[orders_open - 1]:
                orders_open += 1
                
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                    tp = round(avg_entry, 2)
                    
            if curr['high'] >= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                active_trade = False
                continue
                
            elif curr['low'] <= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                active_trade = False

    else:
        close, ema, rsi, raw_atr = prev['close'], prev['EMA_200'], prev['RSI'], prev['ATR']
        has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
        has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
        
        # 🚨 TIME FILTERS
        if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
            if close > ema and rsi <= 31 and has_lower_wick:
                active_trade = True
                direction = "BUY"
                entry_atr = get_fixed_atr(raw_atr)
                current_lot = get_dynamic_lot(entry_atr)
                entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
                sl = entry_price - (12 * entry_atr)
                tp = entry_price + (2 * entry_atr)
                
                layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, 6)]
                orders_open = 1
                
            elif close < ema and rsi >= 69.8 and has_upper_wick:
                active_trade = True
                direction = "SELL"
                entry_atr = get_fixed_atr(raw_atr)
                current_lot = get_dynamic_lot(entry_atr)
                entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
                sl = entry_price + (12 * entry_atr)
                tp = entry_price - (2 * entry_atr)
                
                layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, 6)]
                orders_open = 1

print("="*150)
print(f"📊 SUMMARY | 6-Layer Grid Mode | Dynamic Lot (42 Mult) | Filters Active")
print("="*150)
if (tp_hits + sl_hits) > 0:
    print(f"✅ Wins : {tp_hits} | ❌ Losses: {sl_hits} | 🎯 Win Rate: {(tp_hits/(tp_hits+sl_hits))*100:.2f}%")
    print(f"💰 Net PnL: ${total_pnl:.2f} | 🏦 Final Capital: ${running_capital:.2f}")
else:
    print("⚠️ Ek bhi entry setup nahi mila!")

mt5.shutdown()
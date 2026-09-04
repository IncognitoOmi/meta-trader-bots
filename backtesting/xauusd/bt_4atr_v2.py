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
MAX_RISK = 100.0  
MIN_SAFE_ATR = 1.5  

# 🚨 DYNAMIC GRID SETTINGS (2 Layers = 4 ATR SL)
MAX_LAYERS = 2  
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

# 🕒 TIMEZONE FIX
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df['EMA_200'] = ta.ema(df['close'], length=200)
df['RSI'] = ta.rsi(df['close'], length=9)
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
    return max(MIN_SAFE_ATR, round(adj, 2))

def get_dynamic_lot(fixed_atr):
    calculated_lot = MAX_RISK / (RISK_MULT * fixed_atr * 100.0)
    return max(0.01, min(math.floor(calculated_lot * 100) / 100.0, 10.0))

def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
    contract = 100.0
    pnl = (exit_p - e_p) if dir == "BUY" else (e_p - exit_p)
    
    for i in range(total_orders - 1):
        pnl += (exit_p - l_prices[i]) if dir == "BUY" else (l_prices[i] - exit_p)
        
    return pnl * lot * contract

print("\n" + "="*150)
print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
print("="*150)

for i in range(1, len(df)):
    curr, prev = df.iloc[i], df.iloc[i-1]
    
    curr_ist_time = curr['time']
    time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
    
    if active_trade:
        exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
        entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')
        
        if direction == "BUY":
            while orders_open < MAX_LAYERS and curr['low'] <= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
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
            while orders_open < MAX_LAYERS and curr['high'] >= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
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
        
        # 🚨 ATR FILTER ADDED HERE (raw_atr >= 2.5) 🚨
        if time_hm >= 1130 and not (1700 <= time_hm <= 1800) and raw_atr >= 2.5:
            if close > ema and rsi <= 31 and has_lower_wick:
                direction = "BUY"
                active_trade = True
            elif close < ema and rsi >= 69.8 and has_upper_wick:
                direction = "SELL"
                active_trade = True
                
            if active_trade:
                entry_atr = get_fixed_atr(raw_atr)
                current_lot = get_dynamic_lot(entry_atr)
                entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
                if direction == "BUY":
                    sl = entry_price - (SL_ATR_MULT * entry_atr)
                    tp = entry_price + (2 * entry_atr)
                    layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                else:
                    sl = entry_price + (SL_ATR_MULT * entry_atr)
                    tp = entry_price - (2 * entry_atr)
                    layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                    
                orders_open = 1

print("="*150)
print(f"📊 SUMMARY | {MAX_LAYERS}-Layer Grid Mode | Dynamic Lot ({RISK_MULT} Mult) | Filters Active")
print("="*150)
if (tp_hits + sl_hits) > 0:
    print(f"✅ Wins : {tp_hits} | ❌ Losses: {sl_hits} | 🎯 Win Rate: {(tp_hits/(tp_hits+sl_hits))*100:.2f}%")
    print(f"💰 Net PnL: ${total_pnl:.2f} | 🏦 Final Capital: ${running_capital:.2f}")
else:
    print("⚠️ Ek bhi entry setup nahi mila!")

mt5.shutdown()
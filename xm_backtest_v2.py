import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import math
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM" # Change to XM server if you are trading there

STARTING_CAPITAL = 1000.0  # Your personal $1,000 deposit
MARGIN_CALL_LEVEL = 5.0   # Account blows up if equity drops below $50

# ==========================================
# 🎛️ 2. STRATEGY PARAMETERS (Change these!)
# ==========================================
RISK_PERCENT = 5.0          # Risk 5% of current equity per trade
KILL_SWITCH_PERCENT = -30.0 # Cut the grid if floating loss hits -30% of equity
TP_MULT = 2.0               # Take Profit distance = 2.0 * ATR
LAYER_MULT = 3.0            # Distance between grid layers = 3.0 * ATR

PRINT_TRADES = True         # Set to False if you only want to see the final summary

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 3. FETCH HISTORICAL DATA 
# ==========================================
print("📥 Fetching 10 years of historical data...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=730) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0: 
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

print("⚙️ Calculating Indicators...")
df['EMA_280'] = ta.ema(df['close'], length=285)
df['RSI'] = ta.rsi(df['close'], length=14)
df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# Extract arrays for speed
time_hm_arr = (df['time'].dt.hour * 100 + df['time'].dt.minute).values
time_str_arr = df['time'].dt.strftime('%Y-%m-%d %H:%M').values 
open_arr = df['open'].values
high_arr = df['high'].values
low_arr = df['low'].values
close_arr = df['close'].values
ema_arr = df['EMA_280'].values
rsi_arr = df['RSI'].values
atr_arr = df['ATR'].values
lower_wick_arr = ((df['low'] < df['open']) & (df['low'] < df['close'])).values
upper_wick_arr = ((df['high'] > df['open']) & (df['high'] > df['close'])).values

# ==========================================
# 🧠 4. SIMPLE SIMULATION ENGINE
# ==========================================
def calc_exact_pnl(dir_val, exit_p, e_p, l_prices, total_orders, lot):
    pnl = 0.0
    contract = 100.0
    if dir_val == "BUY":
        pnl += (exit_p - e_p) * lot * contract
        for i in range(total_orders - 1): pnl += (exit_p - l_prices[i]) * lot * contract
    else:
        pnl += (e_p - exit_p) * lot * contract
        for i in range(total_orders - 1): pnl += (l_prices[i] - exit_p) * lot * contract
    return pnl

running_capital = STARTING_CAPITAL
tp_hits = 0
sl_hits = 0
account_blown = False

active_trade = False
direction = ""
entry_price = tp = sl = current_lot = 0.0
orders_open = 0 
layers_prices = []
dynamic_kill_switch_dollar = 0.0
entry_time_str = ""

if PRINT_TRADES:
    print("\n" + "="*140)
    print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<5} | {'LAYERS':<6} | {'RESULT':<7} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
    print("="*140)

for i in range(1, len(df)):
    if active_trade:
        trade_closed = False
        curr_low, curr_high = low_arr[i], high_arr[i]
        exit_time_str = time_str_arr[i]

        if direction == "BUY":
            while orders_open < 6 and curr_low <= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                else:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
            worst_pnl = calc_exact_pnl("BUY", curr_low, entry_price, layers_prices, orders_open, current_lot)
            
            if worst_pnl <= dynamic_kill_switch_dollar:
                sl_hits += 1
                running_capital += dynamic_kill_switch_dollar
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | BUY  | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<5.2f} | {orders_open - 1:<6} | LOSS    | -${abs(dynamic_kill_switch_dollar):<9.2f} | ${running_capital:.2f}")
            
            elif curr_low <= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | BUY  | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<5.2f} | {orders_open - 1:<6} | LOSS    | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
            
            elif curr_high >= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | BUY  | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<5.2f} | {orders_open - 1:<6} | WIN     | +${pnl:<9.2f} | ${running_capital:.2f}")
                
        elif direction == "SELL":
            while orders_open < 6 and curr_high >= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                else:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
            worst_pnl = calc_exact_pnl("SELL", curr_high, entry_price, layers_prices, orders_open, current_lot)
            
            if worst_pnl <= dynamic_kill_switch_dollar:
                sl_hits += 1
                running_capital += dynamic_kill_switch_dollar
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | SELL | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<5.2f} | {orders_open - 1:<6} | LOSS    | -${abs(dynamic_kill_switch_dollar):<9.2f} | ${running_capital:.2f}")
            
            elif curr_high >= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | SELL | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<5.2f} | {orders_open - 1:<6} | LOSS    | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
            
            elif curr_low <= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                trade_closed = True
                if PRINT_TRADES: print(f"{entry_time_str:<19} | SELL | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<5.2f} | {orders_open - 1:<6} | WIN     | +${pnl:<9.2f} | ${running_capital:.2f}")

        if trade_closed:
            active_trade = False
            if running_capital < MARGIN_CALL_LEVEL:
                account_blown = True
                break # Account dead, stop simulating

    else:
        close, ema, rsi, raw_atr = close_arr[i-1], ema_arr[i-1], rsi_arr[i-1], atr_arr[i-1]
        time_hm = time_hm_arr[i]
        
        if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
            if close > ema and rsi <= 31 and lower_wick_arr[i-1]:
                active_trade = True
                direction = "BUY"
                
                adj_atr = raw_atr - 0.5
                entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                
                # 🚀 DYNAMIC COMPOUNDING
                dynamic_risk_dollar = running_capital * (RISK_PERCENT / 100.0)
                dynamic_kill_switch_dollar = -(running_capital * (abs(KILL_SWITCH_PERCENT) / 100.0))
                
                c_lot = dynamic_risk_dollar / (42.0 * entry_atr * 100.0)
                current_lot = math.floor(c_lot * 100.0) / 100.0
                current_lot = max(0.01, min(current_lot, 50.0)) # MT5 constraints
                
                entry_price = open_arr[i]
                entry_time_str = time_str_arr[i]
                
                sl = entry_price - (12.0 * entry_atr)
                tp = entry_price + (TP_MULT * entry_atr)
                layers_prices = [entry_price - (j * LAYER_MULT * entry_atr) for j in range(1, 6)]
                orders_open = 1
                
            elif close < ema and rsi >= 69.8 and upper_wick_arr[i-1]:
                active_trade = True
                direction = "SELL"
                
                adj_atr = raw_atr - 0.5
                entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                
                # 🚀 DYNAMIC COMPOUNDING
                dynamic_risk_dollar = running_capital * (RISK_PERCENT / 100.0)
                dynamic_kill_switch_dollar = -(running_capital * (abs(KILL_SWITCH_PERCENT) / 100.0))
                
                c_lot = dynamic_risk_dollar / (42.0 * entry_atr * 100.0)
                current_lot = math.floor(c_lot * 100.0) / 100.0
                current_lot = max(0.01, min(current_lot, 50.0))
                
                entry_price = open_arr[i]
                entry_time_str = time_str_arr[i]
                
                sl = entry_price + (12.0 * entry_atr)
                tp = entry_price - (TP_MULT * entry_atr)
                layers_prices = [entry_price + (j * LAYER_MULT * entry_atr) for j in range(1, 6)]
                orders_open = 1

# ==========================================
# 🏆 5. FINAL SUMMARY
# ==========================================
print("\n" + "="*80)
print(f"📊 PERSONAL ACCOUNT ($1000 START) SIMULATION SUMMARY")
print("="*80)

if account_blown:
    print(f"💀 MARGIN CALL HIT! Account blown.")
    print(f"🏦 Final Balance before blowing: ${running_capital:.2f}")
else:
    print(f"🏆 ACCOUNT SURVIVED 10 YEARS! 🏆")
    print(f"🏦 Final Balance: ${running_capital:,.2f}")

print("-" * 80)
print(f"✅ Total Wins   : {tp_hits}")
print(f"❌ Total Losses : {sl_hits}")
win_rate = (tp_hits/(tp_hits+sl_hits))*100 if (tp_hits+sl_hits) > 0 else 0
print(f"🎯 Win Rate     : {win_rate:.2f}%")
print("="*80)

mt5.shutdown()
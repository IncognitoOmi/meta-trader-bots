import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import math
from datetime import datetime, timedelta

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
account_login = 11884282
account_password = "T)72+?sV6"
broker_server = "FundingPips2-SIM"

STARTING_CAPITAL = 50000.0
MAX_RISK = 1000.0
MIN_SAFE_ATR = 1.5 

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FundingPips/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 🧠 2. STRATEGY ENGINE (MULTI-TF)
# ==========================================
def get_fixed_atr(raw_atr):
    adj = raw_atr - 0.5
    return MIN_SAFE_ATR if adj < MIN_SAFE_ATR else round(adj, 2)

def get_dynamic_lot(fixed_atr):
    calculated_lot = MAX_RISK / (12 * fixed_atr * 100.0)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    return max(0.01, min(final_lot, 10.0))

def calc_exact_pnl(dir, exit_p, e_p, l1, l2, total_orders, lot):
    pnl = 0.0
    contract = 100.0
    if dir == "BUY":
        pnl += (exit_p - e_p) * lot * contract
        if total_orders >= 2: pnl += (exit_p - l1) * lot * contract
        if total_orders == 3: pnl += (exit_p - l2) * lot * contract
    else:
        pnl += (e_p - exit_p) * lot * contract
        if total_orders >= 2: pnl += (l1 - exit_p) * lot * contract
        if total_orders == 3: pnl += (l2 - exit_p) * lot * contract
    return pnl

def run_backtest_for_tf(timeframe, tf_name, start_date, end_date):
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    if rates is None or len(rates) == 0: return []
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    trades = []
    active_trade = False
    direction = ""
    entry_price = tp = sl = layer1 = layer2 = current_lot = entry_rsi = entry_atr = 0
    orders_open = 0 
    entry_time = None

    for i in range(1, len(df)):
        curr, prev = df.iloc[i], df.iloc[i-1]
        curr_ist_time = curr['time'] + timedelta(hours=2, minutes=30)
        
        if active_trade:
            if direction == "BUY":
                if orders_open == 1 and curr['low'] <= layer1: orders_open = 2; tp = entry_price 
                if orders_open == 2 and curr['low'] <= layer2: orders_open = 3; tp = entry_price 
                    
                if curr['low'] <= sl:
                    orders_open = 3 
                    pnl = calc_exact_pnl("BUY", sl, entry_price, layer1, layer2, orders_open, current_lot)
                    trades.append({'entry_time': entry_time, 'tf': tf_name, 'type': 'BUY', 'rsi': entry_rsi, 'atr': entry_atr, 'entry': entry_price, 'exit_time': curr_ist_time, 'exit': sl, 'lot': current_lot, 'layers': orders_open - 1, 'result': 'LOSS', 'pnl': pnl})
                    active_trade = False
                    continue
                elif curr['high'] >= tp:
                    pnl = calc_exact_pnl("BUY", tp, entry_price, layer1, layer2, orders_open, current_lot)
                    trades.append({'entry_time': entry_time, 'tf': tf_name, 'type': 'BUY', 'rsi': entry_rsi, 'atr': entry_atr, 'entry': entry_price, 'exit_time': curr_ist_time, 'exit': tp, 'lot': current_lot, 'layers': orders_open - 1, 'result': 'WIN', 'pnl': pnl})
                    active_trade = False
                    
            elif direction == "SELL":
                if orders_open == 1 and curr['high'] >= layer1: orders_open = 2; tp = entry_price 
                if orders_open == 2 and curr['high'] >= layer2: orders_open = 3; tp = entry_price 
                    
                if curr['high'] >= sl:
                    orders_open = 3 
                    pnl = calc_exact_pnl("SELL", sl, entry_price, layer1, layer2, orders_open, current_lot)
                    trades.append({'entry_time': entry_time, 'tf': tf_name, 'type': 'SELL', 'rsi': entry_rsi, 'atr': entry_atr, 'entry': entry_price, 'exit_time': curr_ist_time, 'exit': sl, 'lot': current_lot, 'layers': orders_open - 1, 'result': 'LOSS', 'pnl': pnl})
                    active_trade = False
                    continue
                elif curr['low'] <= tp:
                    pnl = calc_exact_pnl("SELL", tp, entry_price, layer1, layer2, orders_open, current_lot)
                    trades.append({'entry_time': entry_time, 'tf': tf_name, 'type': 'SELL', 'rsi': entry_rsi, 'atr': entry_atr, 'entry': entry_price, 'exit_time': curr_ist_time, 'exit': tp, 'lot': current_lot, 'layers': orders_open - 1, 'result': 'WIN', 'pnl': pnl})
                    active_trade = False

        else:
            close, ema, rsi, raw_atr = prev['close'], prev['EMA_200'], prev['RSI'], prev['ATR']
            has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
            has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
            
            time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
            
            if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                if close > ema and rsi <= 31 and has_lower_wick:
                    active_trade, direction = True, "BUY"
                    entry_atr = get_fixed_atr(raw_atr)
                    current_lot = get_dynamic_lot(entry_atr)
                    entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                    sl = entry_price - (6 * entry_atr)
                    tp = entry_price + (2 * entry_atr)
                    layer1, layer2 = entry_price - (2 * entry_atr), entry_price - (4 * entry_atr)
                    orders_open = 1
                    
                elif close < ema and rsi >= 69.8 and has_upper_wick:
                    active_trade, direction = True, "SELL"
                    entry_atr = get_fixed_atr(raw_atr)
                    current_lot = get_dynamic_lot(entry_atr)
                    entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                    sl = entry_price + (6 * entry_atr)
                    tp = entry_price - (2 * entry_atr)
                    layer1, layer2 = entry_price + (2 * entry_atr), entry_price + (4 * entry_atr)
                    orders_open = 1
                    
    return trades

# ==========================================
# 🚀 3. EXECUTE & PRINT RESULTS
# ==========================================
end_date = datetime.now()
start_date = end_date - timedelta(days=63)

# Run logic for all 3 Timeframes
m1_trades = run_backtest_for_tf(mt5.TIMEFRAME_M1, "M1", start_date, end_date)
m5_trades = run_backtest_for_tf(mt5.TIMEFRAME_M5, "M5", start_date, end_date)
m15_trades = run_backtest_for_tf(mt5.TIMEFRAME_M15, "M15", start_date, end_date)

all_trades = m1_trades + m5_trades + m15_trades
all_trades.sort(key=lambda x: x['entry_time']) # Sort by exact Entry Time

print("\n" + "="*142)
print(f"{'ENTRY TIME (IST)':<20} | {'TF':<3} | {'TYPE':<4} | {'RSI':<5} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<20} | {'EXIT':<8} | {'LOT':<5} | {'LAYERS':<6} | {'RESULT':<6} | {'PNL'}")
print("="*142)

total_pnl = 0.0
wins = 0
losses = 0

for t in all_trades:
    total_pnl += t['pnl']
    if t['result'] == 'WIN': wins += 1
    else: losses += 1
    
    print(f"{str(t['entry_time']):<20} | {t['tf']:<3} | {t['type']:<4} | {t['rsi']:<5.1f} | {t['atr']:<4.2f} | {t['entry']:<8.2f} | {str(t['exit_time']):<20} | {t['exit']:<8.2f} | {t['lot']:<5.2f} | {t['layers']:<6} | {t['result']:<6} | ${t['pnl']:.2f}")

final_capital = STARTING_CAPITAL + total_pnl

print("="*142)
print(f"📊 63-DAY SUMMARY (MULTI-TF) | $50K | $1K Risk | Filters: >11:30 AM, No 5-6 PM, Min ATR 1.5")
print("="*142)
total = wins + losses
if total > 0:
    print(f"✅ Wins : {wins} | ❌ Losses: {losses} | 🎯 Win Rate: {(wins/total)*100:.2f}%")
    print(f"💰 Net PnL: ${total_pnl:.2f} | 🏦 Final Capital: ${final_capital:.2f}")
else:
    print("⚠️ Ek bhi entry setup nahi mila!")

mt5.shutdown()
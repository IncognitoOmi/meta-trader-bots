import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import math
import itertools
from numba import njit
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"

# ==========================================
# 🔬 2. OPTIMIZER GRID SETTINGS
# ==========================================
PARAM_GRID = {
    'INITIAL_MAX_RISK': range(100, 600, 100),
    'INITIAL_MAX_FLOATING_LOSS': range(-300, -50, 50),
    'POST_PAYOUT_MAX_RISK': range(100, 400, 100),
    'POST_PAYOUT_MAX_FLOATING_LOSS': range(-200, -40, 40)
}

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 3. FETCH DATA & PRE-COMPUTE
# ==========================================
print("📥 Fetching 10 years of M1 data...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=3650) 

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

# 🚀 PURE NUMERIC ARRAYS FOR NUMBA C-COMPILER
time_hm_arr = (df['time'].dt.hour * 100 + df['time'].dt.minute).values.astype(np.int32)
date_int_arr = df['time'].dt.strftime('%Y%m%d').astype(np.int32).values 
open_arr = df['open'].values.astype(np.float64)
high_arr = df['high'].values.astype(np.float64)
low_arr = df['low'].values.astype(np.float64)
close_arr = df['close'].values.astype(np.float64)
ema_arr = df['EMA_280'].values.astype(np.float64)
rsi_arr = df['RSI'].values.astype(np.float64)
atr_arr = df['ATR'].values.astype(np.float64)
lower_wick_arr = ((df['low'] < df['open']) & (df['low'] < df['close'])).values.astype(np.bool_)
upper_wick_arr = ((df['high'] > df['open']) & (df['high'] > df['close'])).values.astype(np.bool_)

start_indices = []
for y in range(1, 11):
    target_date_str = (end_date - timedelta(days=y*365)).strftime('%Y%m%d')
    idx = np.argmax(date_int_arr >= int(target_date_str))
    start_indices.append(idx)
start_indices_arr = np.array(start_indices, dtype=np.int32)

# ==========================================
# ⚡ 4. NUMBA C-COMPILED CORE (1000x FASTER)
# ==========================================
@njit
def calc_pnl_fast(dir_val, exit_p, e_p, l_prices, total_orders, lot):
    pnl = 0.0
    contract = 100.0
    if dir_val == 1: # BUY
        pnl += (exit_p - e_p) * lot * contract
        for i in range(total_orders - 1): pnl += (exit_p - l_prices[i]) * lot * contract
    else: # SELL
        pnl += (e_p - exit_p) * lot * contract
        for i in range(total_orders - 1): pnl += (l_prices[i] - exit_p) * lot * contract
    return pnl

@njit
def run_fast_simulation(init_risk, init_loss, post_risk, post_loss, start_idx, 
                        date_arr, time_arr, o_arr, h_arr, l_arr, c_arr, e_arr, r_arr, a_arr, lw_arr, uw_arr):
    
    tp_hits, sl_hits = 0, 0
    running_capital = 25000.0
    start_of_day_balance = 25000.0
    daily_floor = start_of_day_balance - 750.0
    overall_floor = 24000.0
    
    current_day = -1
    unique_trading_days = 0
    last_traded_day = -1
    payout_count = 0
    total_extracted = 0.0
    
    current_max_risk = float(init_risk)
    current_max_floating_loss = float(init_loss)
    
    active_trade = False
    direction = 0
    entry_price = tp = sl = current_lot = 0.0
    orders_open = 0 
    layers_prices = np.zeros(5)

    for i in range(max(1, start_idx), len(date_arr)):
        curr_date = date_arr[i]
        
        if curr_date != current_day:
            current_day = curr_date
            start_of_day_balance = running_capital
            daily_floor = start_of_day_balance - 750.0
        
        if active_trade:
            trade_closed = False
            curr_low, curr_high = l_arr[i], h_arr[i]

            if direction == 1: # BUY
                while orders_open < 6 and curr_low <= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = round(entry_price, 2)
                    else:
                        sum_l = 0.0
                        for k in range(orders_open - 1): sum_l += layers_prices[k]
                        tp = round((entry_price + sum_l) / orders_open, 2)
                        
                worst_pnl = calc_pnl_fast(1, curr_low, entry_price, layers_prices, orders_open, current_lot)
                
                if worst_pnl <= current_max_floating_loss:
                    sl_hits += 1; running_capital += current_max_floating_loss; trade_closed = True
                elif curr_low <= sl:
                    sl_hits += 1; running_capital += calc_pnl_fast(1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                elif curr_high >= tp:
                    tp_hits += 1; running_capital += calc_pnl_fast(1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                    
            elif direction == -1: # SELL
                while orders_open < 6 and curr_high >= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = round(entry_price, 2)
                    else:
                        sum_l = 0.0
                        for k in range(orders_open - 1): sum_l += layers_prices[k]
                        tp = round((entry_price + sum_l) / orders_open, 2)
                        
                worst_pnl = calc_pnl_fast(-1, curr_high, entry_price, layers_prices, orders_open, current_lot)
                
                if worst_pnl <= current_max_floating_loss:
                    sl_hits += 1; running_capital += current_max_floating_loss; trade_closed = True
                elif curr_high >= sl:
                    sl_hits += 1; running_capital += calc_pnl_fast(-1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                elif curr_low <= tp:
                    tp_hits += 1; running_capital += calc_pnl_fast(-1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True

            if trade_closed:
                active_trade = False
                if last_traded_day != curr_date:
                    unique_trading_days += 1
                    last_traded_day = curr_date
                
                if running_capital < daily_floor or running_capital < overall_floor:
                    return False, running_capital, total_extracted, tp_hits, sl_hits
                    
                if running_capital >= 27500.0 and unique_trading_days >= 10:
                    running_capital -= 250.0
                    total_extracted += 250.0
                    payout_count += 1
                    
                    if payout_count == 1:
                        overall_floor = 25000.0 
                        current_max_risk = float(post_risk)
                        current_max_floating_loss = float(post_loss)
                    
                    unique_trading_days = 0
                    start_of_day_balance = running_capital 
                    daily_floor = start_of_day_balance - 750.0

        else:
            close = c_arr[i-1]
            ema = e_arr[i-1]
            rsi = r_arr[i-1]
            raw_atr = a_arr[i-1]
            time_hm = time_arr[i]
            
            if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                if close > ema and rsi <= 31 and lw_arr[i-1]:
                    active_trade, direction = True, 1
                    adj_atr = raw_atr - 0.5
                    entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
                    c_lot = current_max_risk / (42.0 * entry_atr * 100.0)
                    current_lot = math.floor(c_lot * 100.0) / 100.0
                    if current_lot < 0.01: current_lot = 0.01
                    if current_lot > 10.0: current_lot = 10.0
                    
                    entry_price = o_arr[i]
                    sl, tp = entry_price - (12.0 * entry_atr), entry_price + (2.0 * entry_atr)
                    for j in range(1, 6): layers_prices[j-1] = entry_price - (j * 2.0 * entry_atr)
                    orders_open = 1
                    
                elif close < ema and rsi >= 69.8 and uw_arr[i-1]:
                    active_trade, direction = True, -1
                    adj_atr = raw_atr - 0.5
                    entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
                    c_lot = current_max_risk / (42.0 * entry_atr * 100.0)
                    current_lot = math.floor(c_lot * 100.0) / 100.0
                    if current_lot < 0.01: current_lot = 0.01
                    if current_lot > 10.0: current_lot = 10.0
                    
                    entry_price = o_arr[i]
                    sl, tp = entry_price + (12.0 * entry_atr), entry_price - (2.0 * entry_atr)
                    for j in range(1, 6): layers_prices[j-1] = entry_price + (j * 2.0 * entry_atr)
                    orders_open = 1

    return True, running_capital, total_extracted, tp_hits, sl_hits

# ==========================================
# 🚀 5. EXECUTE GRID SEARCH 
# ==========================================
keys, values = zip(*PARAM_GRID.items())
permutations = [dict(zip(keys, v)) for v in itertools.product(*values)]
total_tests = len(permutations)

print(f"\n🧪 Starting Numba C-Compiled Multi-Start Optimizer...")
print(f"🔄 Testing {total_tests} combinations across 10 years (Compiling C-code on first loop...)")

best_params = None
highest_avg_extracted = -1

for idx, params in enumerate(permutations):
    if idx % 100 == 0: print(f"⚡ Processing {idx}/{total_tests} grids instantly...")
        
    survived_all = True
    total_money = 0
    
    for start_idx in start_indices_arr:
        survived, final_cap, money_extracted, wins, losses = run_fast_simulation(
            params['INITIAL_MAX_RISK'], params['INITIAL_MAX_FLOATING_LOSS'],
            params['POST_PAYOUT_MAX_RISK'], params['POST_PAYOUT_MAX_FLOATING_LOSS'],
            start_idx, date_int_arr, time_hm_arr, open_arr, high_arr, low_arr, 
            close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr
        )
        
        if not survived:
            survived_all = False
            break 
            
        total_money += money_extracted
        
    if survived_all:
        avg_money = total_money / 10
        if avg_money > highest_avg_extracted:
            highest_avg_extracted = avg_money
            best_params = params

if best_params is None:
    print("\n💀 NO PARAMETERS SURVIVED ALL 10 STARTING SCENARIOS.")
else:
    print("\n" + "="*80)
    print("🏆 BEST PARAMETERS FOUND (SURVIVED ALL 10 STARTING YEARS)")
    print("="*80)
    print(f"INITIAL_MAX_RISK              = {best_params['INITIAL_MAX_RISK']}")
    print(f"INITIAL_MAX_FLOATING_LOSS     = {best_params['INITIAL_MAX_FLOATING_LOSS']}")
    print(f"POST_PAYOUT_MAX_RISK          = {best_params['POST_PAYOUT_MAX_RISK']}")
    print(f"POST_PAYOUT_MAX_FLOATING_LOSS = {best_params['POST_PAYOUT_MAX_FLOATING_LOSS']}")
    print("="*80)

mt5.shutdown()
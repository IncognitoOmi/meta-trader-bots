# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import numpy as np
# import math
# import itertools
# from numba import njit
# from datetime import datetime, timedelta, timezone

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# account_login = 12219217
# account_password = "1Mz$YuVGJ"
# broker_server = "FundingPips2-SIM"

# # PROP FIRM CONSTRAINTS (1-STEP $25,000 ACCOUNT)
# STARTING_CAPITAL = 25000.0
# DAILY_DD_LIMIT = 750.0          # 3%
# EVAL_TRAILING_DD = 1500.0       # 6%
# EVAL_TARGET = 27500.0           # 10%
# MASTER_OVERALL_FLOOR = 24000.0  # 4%
# MASTER_PAYOUT_TARGET = 27500.0  # 10%
# MASTER_TRAPDOOR_FLOOR = 25000.0 # Floor after 1st payout

# # ==========================================
# # 🔬 2. TARGETED PARAMETER GRIDS
# # ==========================================
# # Phase 1: EVALUATION (Aggressive to pass in weeks/months)
# EVAL_GRID = {
#     'RISK': [300, 400, 500, 600],
#     'LOSS': [-150, -200, -250, -350]
# }

# # Phase 2: MASTER PRE-PAYOUT (Tighter to protect the $1,000 buffer)
# BUFFER_GRID = {
#     'RISK': [150, 200, 250],
#     'LOSS': [-80, -100, -120, -150]
# }

# # Phase 3: MASTER POST-PAYOUT (Balanced to exploit the $2,250 buffer)
# POST_GRID = {
#     'RISK': [200, 250, 300, 400],
#     'LOSS': [-100, -150, -200]
# }

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()

# # ==========================================
# # 📊 3. FETCH HISTORICAL DATA & PRE-COMPUTE
# # ==========================================
# print("📥 Fetching historical data...")
# end_date = datetime.now(timezone.utc)
# start_date = end_date - timedelta(days=3650) 

# rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
# if rates is None or len(rates) == 0: 
#     print("❌ No Data Fetched! Check your broker connection.")
#     quit()

# df = pd.DataFrame(rates)
# df['time'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

# print("⚙️ Calculating Indicators...")
# df['EMA_280'] = ta.ema(df['close'], length=285)
# df['RSI'] = ta.rsi(df['close'], length=14)
# df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
# df.dropna(inplace=True)
# df.reset_index(drop=True, inplace=True)

# time_hm_arr = (df['time'].dt.hour * 100 + df['time'].dt.minute).values.astype(np.int32)
# date_int_arr = df['time'].dt.strftime('%Y%m%d').astype(np.int32).values 
# open_arr = df['open'].values.astype(np.float64)
# high_arr = df['high'].values.astype(np.float64)
# low_arr = df['low'].values.astype(np.float64)
# close_arr = df['close'].values.astype(np.float64)
# ema_arr = df['EMA_280'].values.astype(np.float64)
# rsi_arr = df['RSI'].values.astype(np.float64)
# atr_arr = df['ATR'].values.astype(np.float64)
# lower_wick_arr = ((df['low'] < df['open']) & (df['low'] < df['close'])).values.astype(np.bool_)
# upper_wick_arr = ((df['high'] > df['open']) & (df['high'] > df['close'])).values.astype(np.bool_)

# # Detect how many years of historical data the broker actually provided
# total_calendar_days = (df['time'].iloc[-1] - df['time'].iloc[0]).days
# years_available = min(10, max(1, total_calendar_days // 365))
# print(f"📊 Available Historical Data: {years_available} Year(s) ({len(df):,} candles)")

# start_indices = []
# for y in range(1, years_available + 1):
#     target_date_str = (end_date - timedelta(days=y*365)).strftime('%Y%m%d')
#     idx = np.argmax(date_int_arr >= int(target_date_str))
#     start_indices.append(idx)
# start_indices_arr = np.array(start_indices, dtype=np.int32)

# # ==========================================
# # ⚡ 4. NUMBA FAST ENGINES (C-COMPILED)
# # ==========================================
# @njit
# def calc_pnl_fast(dir_val, exit_p, e_p, l_prices, total_orders, lot):
#     pnl = 0.0
#     contract = 100.0
#     if dir_val == 1:
#         pnl += (exit_p - e_p) * lot * contract
#         for i in range(total_orders - 1): pnl += (exit_p - l_prices[i]) * lot * contract
#     else:
#         pnl += (e_p - exit_p) * lot * contract
#         for i in range(total_orders - 1): pnl += (l_prices[i] - exit_p) * lot * contract
#     return pnl

# @njit
# def simulate_phase(start_idx, mode, risk_val, loss_val,
#                    date_arr, time_arr, o_arr, h_arr, l_arr, c_arr, e_arr, r_arr, a_arr, lw_arr, uw_arr):
#     # mode: 1 = EVAL, 2 = BUFFER CREATION, 3 = POST PAYOUT
#     running_capital = 25000.0 if mode != 3 else 27250.0
#     start_of_day_balance = running_capital
#     daily_floor = start_of_day_balance - 750.0
    
#     high_watermark = running_capital
#     eval_trailing_floor = running_capital - 1500.0
#     overall_floor = 24000.0 if mode == 2 else 25000.0
    
#     current_day = -1
#     unique_trading_days = 0
#     last_traded_day = -1
#     days_elapsed = 0
#     total_payouts = 0.0
    
#     active_trade = False
#     direction = 0
#     entry_price = tp = sl = current_lot = 0.0
#     orders_open = 0 
#     layers_prices = np.zeros(5)

#     for i in range(max(1, start_idx), len(date_arr)):
#         curr_date = date_arr[i]
        
#         if curr_date != current_day:
#             current_day = curr_date
#             start_of_day_balance = running_capital
#             daily_floor = start_of_day_balance - 750.0
#             days_elapsed += 1
            
#         if active_trade:
#             trade_closed = False
#             curr_low, curr_high = l_arr[i], h_arr[i]

#             if direction == 1:
#                 while orders_open < 6 and curr_low <= layers_prices[orders_open - 1]:
#                     orders_open += 1
#                     if 2 <= orders_open <= 4:
#                         tp = round(entry_price, 2)
#                     else:
#                         sum_l = 0.0
#                         for k in range(orders_open - 1): sum_l += layers_prices[k]
#                         tp = round((entry_price + sum_l) / orders_open, 2)
                        
#                 worst_pnl = calc_pnl_fast(1, curr_low, entry_price, layers_prices, orders_open, current_lot)
#                 if worst_pnl <= loss_val:
#                     running_capital += loss_val; trade_closed = True
#                 elif curr_low <= sl:
#                     running_capital += calc_pnl_fast(1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
#                 elif curr_high >= tp:
#                     running_capital += calc_pnl_fast(1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True

#             elif direction == -1:
#                 while orders_open < 6 and curr_high >= layers_prices[orders_open - 1]:
#                     orders_open += 1
#                     if 2 <= orders_open <= 4:
#                         tp = round(entry_price, 2)
#                     else:
#                         sum_l = 0.0
#                         for k in range(orders_open - 1): sum_l += layers_prices[k]
#                         tp = round((entry_price + sum_l) / orders_open, 2)
                        
#                 worst_pnl = calc_pnl_fast(-1, curr_high, entry_price, layers_prices, orders_open, current_lot)
#                 if worst_pnl <= loss_val:
#                     running_capital += loss_val; trade_closed = True
#                 elif curr_high >= sl:
#                     running_capital += calc_pnl_fast(-1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
#                 elif curr_low <= tp:
#                     running_capital += calc_pnl_fast(-1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True

#             if trade_closed:
#                 active_trade = False
#                 if last_traded_day != curr_date:
#                     unique_trading_days += 1
#                     last_traded_day = curr_date

#                 # DRAWDOWN BREACH CHECKS
#                 if mode == 1: # EVAL
#                     if running_capital > high_watermark:
#                         high_watermark = running_capital
#                         new_floor = high_watermark - 1500.0
#                         if new_floor > eval_trailing_floor: eval_trailing_floor = new_floor
#                     if running_capital < daily_floor or running_capital < eval_trailing_floor:
#                         return False, 99999.0
#                     if running_capital >= 27500.0:
#                         return True, float(days_elapsed)
                
#                 elif mode == 2: # BUFFER CREATION (PRE-PAYOUT)
#                     if running_capital < daily_floor or running_capital < overall_floor:
#                         return False, 99999.0
#                     if running_capital >= 27500.0 and unique_trading_days >= 10:
#                         return True, float(days_elapsed)

#                 elif mode == 3: # POST-PAYOUT SURVIVAL
#                     if running_capital < daily_floor or running_capital < overall_floor:
#                         return False, total_payouts
#                     if running_capital >= 27500.0 and unique_trading_days >= 10:
#                         running_capital -= 250.0
#                         total_payouts += 250.0
#                         unique_trading_days = 0
#                         start_of_day_balance = running_capital
#                         daily_floor = start_of_day_balance - 750.0

#         else:
#             close, ema, rsi, raw_atr = c_arr[i-1], e_arr[i-1], r_arr[i-1], a_arr[i-1]
#             time_hm = time_arr[i]
#             if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#                 if close > ema and rsi <= 31 and lw_arr[i-1]:
#                     active_trade, direction = True, 1
#                     adj_atr = raw_atr - 0.5
#                     entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
#                     c_lot = risk_val / (42.0 * entry_atr * 100.0)
#                     current_lot = math.floor(c_lot * 100.0) / 100.0
#                     if current_lot < 0.01: current_lot = 0.01
#                     if current_lot > 10.0: current_lot = 10.0
#                     entry_price = o_arr[i]
#                     sl, tp = entry_price - (12.0 * entry_atr), entry_price + (2.0 * entry_atr)
#                     for j in range(1, 6): layers_prices[j-1] = entry_price - (j * 2.0 * entry_atr)
#                     orders_open = 1
#                 elif close < ema and rsi >= 69.8 and uw_arr[i-1]:
#                     active_trade, direction = True, -1
#                     adj_atr = raw_atr - 0.5
#                     entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
#                     c_lot = risk_val / (42.0 * entry_atr * 100.0)
#                     current_lot = math.floor(c_lot * 100.0) / 100.0
#                     if current_lot < 0.01: current_lot = 0.01
#                     if current_lot > 10.0: current_lot = 10.0
#                     entry_price = o_arr[i]
#                     sl, tp = entry_price + (12.0 * entry_atr), entry_price - (2.0 * entry_atr)
#                     for j in range(1, 6): layers_prices[j-1] = entry_price + (j * 2.0 * entry_atr)
#                     orders_open = 1

#     if mode == 3:
#         return True, total_payouts
#     return False, 99999.0

# # ==========================================
# # 🚀 5. EXECUTE 3-PHASE GRID SEARCH
# # ==========================================
# print("\n" + "="*80)
# print("🔍 OPTIMIZING PHASE 1: 1-STEP EVALUATION (Fastest Pass)")
# print("="*80)

# eval_combos = list(itertools.product(EVAL_GRID['RISK'], EVAL_GRID['LOSS']))
# best_eval_params, fastest_eval_days = None, 99999.0

# for r, l in eval_combos:
#     all_passed, total_days = True, 0.0
#     for s_idx in start_indices_arr:
#         passed, days = simulate_phase(s_idx, 1, float(r), float(l),
#                                       date_int_arr, time_hm_arr, open_arr, high_arr, low_arr,
#                                       close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr)
#         if not passed:
#             all_passed = False; break
#         total_days += days
#     if all_passed:
#         avg_days = total_days / len(start_indices_arr)
#         if avg_days < fastest_eval_days:
#             fastest_eval_days = avg_days
#             best_eval_params = (r, l)

# print("\n" + "="*80)
# print("🔍 OPTIMIZING PHASE 2: BUFFER CREATION (Pre-Payout Safety)")
# print("="*80)

# buf_combos = list(itertools.product(BUFFER_GRID['RISK'], BUFFER_GRID['LOSS']))
# best_buf_params, fastest_buf_days = None, 99999.0

# for r, l in buf_combos:
#     all_passed, total_days = True, 0.0
#     for s_idx in start_indices_arr:
#         passed, days = simulate_phase(s_idx, 2, float(r), float(l),
#                                       date_int_arr, time_hm_arr, open_arr, high_arr, low_arr,
#                                       close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr)
#         if not passed:
#             all_passed = False; break
#         total_days += days
#     if all_passed:
#         avg_days = total_days / len(start_indices_arr)
#         if avg_days < fastest_buf_days:
#             fastest_buf_days = avg_days
#             best_buf_params = (r, l)

# print("\n" + "="*80)
# print("🔍 OPTIMIZING PHASE 3: POST-PAYOUT (Continuous Survival)")
# print("="*80)

# post_combos = list(itertools.product(POST_GRID['RISK'], POST_GRID['LOSS']))
# best_post_params, max_extracted = None, -1.0

# for r, l in post_combos:
#     all_survived, total_payouts = True, 0.0
#     for s_idx in start_indices_arr:
#         survived, payouts = simulate_phase(s_idx, 3, float(r), float(l),
#                                            date_int_arr, time_hm_arr, open_arr, high_arr, low_arr,
#                                            close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr)
#         if not survived:
#             all_survived = False; break
#         total_payouts += payouts
#     if all_survived:
#         avg_payouts = total_payouts / len(start_indices_arr)
#         if avg_payouts > max_extracted:
#             max_extracted = avg_payouts
#             best_post_params = (r, l)

# # ==========================================
# # 🏆 6. FINAL RESULTS SUMMARY (IN MONTHS)
# # ==========================================
# print("\n" + "="*80)
# print("🏆 OPTIMAL PARAMETERS & TIMELINE BLUEPRINT")
# print("="*80)

# if best_eval_params:
#     eval_months = round(fastest_eval_days / 30.4, 1)
#     print(f"1️⃣ EVALUATION PHASE PARAMETERS:")
#     print(f"   • EVAL_MAX_RISK          = {best_eval_params[0]}")
#     print(f"   • EVAL_MAX_FLOATING_LOSS = {best_eval_params[1]}")
#     print(f"   ⏱️ Expected Time to Pass  = {eval_months} Months (~{int(fastest_eval_days)} calendar days)")
# else:
#     print("1️⃣ EVALUATION PHASE: No tested combo passed across all cohorts.")

# print("-" * 80)
# if best_buf_params:
#     buf_months = round(fastest_buf_days / 30.4, 1)
#     print(f"2️⃣ BUFFER CREATION (PRE-PAYOUT) PARAMETERS:")
#     print(f"   • MASTER_MAX_RISK          = {best_buf_params[0]}")
#     print(f"   • MASTER_MAX_FLOATING_LOSS = {best_buf_params[1]}")
#     print(f"   ⏱️ Expected Time to Payout 1 = {buf_months} Months (~{int(fastest_buf_days)} calendar days)")
# else:
#     print("2️⃣ BUFFER CREATION: No tested combo survived the $1,000 floor.")

# print("-" * 80)
# if best_post_params:
#     print(f"3️⃣ POST-PAYOUT HARVESTING PARAMETERS:")
#     print(f"   • POST_PAYOUT_MAX_RISK          = {best_post_params[0]}")
#     print(f"   • POST_PAYOUT_MAX_FLOATING_LOSS = {best_post_params[1]}")
#     print(f"   💰 Average Payouts Extracted    = ${max_extracted:,.2f}")
# else:
#     print("3️⃣ POST-PAYOUT: No combo survived the $25,000 trapdoor.")
# print("="*80)

# mt5.shutdown()

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
broker_server = "FundingPips2-SIM" # Replace with XM server if pulling from there

# ==========================================
# 🔬 2. MICRO-ACCOUNT GRID (FOR $500)
# ==========================================
PARAM_GRID = {
    'RISK': [5, 10, 15, 20, 30, 40],               # Risk per trade ($)
    'LOSS_KILL_SWITCH': [-50, -75, -100, -150, -250], # Floating loss limit ($)
    'TP_MULT': [1.0, 1.5, 2.0],                    # Take profit speed
    'LAYER_MULT': [2.0, 3.0, 4.0, 5.0]             # Grid distance to survive spikes
}

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 3. FETCH HISTORICAL DATA
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
# ⚡ 4. NUMBA C-COMPILED CORE (PERSONAL ACCOUNT)
# ==========================================
@njit
def calc_pnl_fast(dir_val, exit_p, e_p, l_prices, total_orders, lot):
    pnl = 0.0
    contract = 100.0
    if dir_val == 1:
        pnl += (exit_p - e_p) * lot * contract
        for i in range(total_orders - 1): pnl += (exit_p - l_prices[i]) * lot * contract
    else:
        pnl += (e_p - exit_p) * lot * contract
        for i in range(total_orders - 1): pnl += (l_prices[i] - exit_p) * lot * contract
    return pnl

@njit
def run_personal_simulation(risk_val, loss_val, tp_mult, layer_mult, start_idx, 
                            date_arr, time_arr, o_arr, h_arr, l_arr, c_arr, e_arr, r_arr, a_arr, lw_arr, uw_arr):
    
    running_capital = 500.0  # 💰 Starting with $500
    margin_call_level = 50.0 # 💀 Account blows if equity drops below $50
    
    active_trade = False
    direction = 0
    entry_price = tp = sl = current_lot = 0.0
    orders_open = 0 
    layers_prices = np.zeros(5)

    for i in range(max(1, start_idx), len(date_arr)):
        if active_trade:
            trade_closed = False
            curr_low, curr_high = l_arr[i], h_arr[i]

            if direction == 1:
                while orders_open < 6 and curr_low <= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = round(entry_price, 2)
                    else:
                        sum_l = 0.0
                        for k in range(orders_open - 1): sum_l += layers_prices[k]
                        tp = round((entry_price + sum_l) / orders_open, 2)
                        
                worst_pnl = calc_pnl_fast(1, curr_low, entry_price, layers_prices, orders_open, current_lot)
                
                if worst_pnl <= loss_val:
                    running_capital += loss_val; trade_closed = True
                elif curr_low <= sl:
                    running_capital += calc_pnl_fast(1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                elif curr_high >= tp:
                    running_capital += calc_pnl_fast(1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                    
            elif direction == -1:
                while orders_open < 6 and curr_high >= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = round(entry_price, 2)
                    else:
                        sum_l = 0.0
                        for k in range(orders_open - 1): sum_l += layers_prices[k]
                        tp = round((entry_price + sum_l) / orders_open, 2)
                        
                worst_pnl = calc_pnl_fast(-1, curr_high, entry_price, layers_prices, orders_open, current_lot)
                
                if worst_pnl <= loss_val:
                    running_capital += loss_val; trade_closed = True
                elif curr_high >= sl:
                    running_capital += calc_pnl_fast(-1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
                elif curr_low <= tp:
                    running_capital += calc_pnl_fast(-1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True

            if trade_closed:
                active_trade = False
                # Margin Call Check
                if running_capital < margin_call_level:
                    return False, running_capital

        else:
            close, ema, rsi, raw_atr = c_arr[i-1], e_arr[i-1], r_arr[i-1], a_arr[i-1]
            time_hm = time_arr[i]
            
            if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                if close > ema and rsi <= 31 and lw_arr[i-1]:
                    active_trade, direction = True, 1
                    adj_atr = raw_atr - 0.5
                    entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
                    c_lot = risk_val / (42.0 * entry_atr * 100.0)
                    current_lot = math.floor(c_lot * 100.0) / 100.0
                    if current_lot < 0.01: current_lot = 0.01 # MT5 strict minimum
                    if current_lot > 10.0: current_lot = 10.0
                    
                    entry_price = o_arr[i]
                    sl, tp = entry_price - (12.0 * entry_atr), entry_price + (tp_mult * entry_atr)
                    for j in range(1, 6): layers_prices[j-1] = entry_price - (j * layer_mult * entry_atr)
                    orders_open = 1
                    
                elif close < ema and rsi >= 69.8 and uw_arr[i-1]:
                    active_trade, direction = True, -1
                    adj_atr = raw_atr - 0.5
                    entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
                    c_lot = risk_val / (42.0 * entry_atr * 100.0)
                    current_lot = math.floor(c_lot * 100.0) / 100.0
                    if current_lot < 0.01: current_lot = 0.01
                    if current_lot > 10.0: current_lot = 10.0
                    
                    entry_price = o_arr[i]
                    sl, tp = entry_price + (12.0 * entry_atr), entry_price - (tp_mult * entry_atr)
                    for j in range(1, 6): layers_prices[j-1] = entry_price + (j * layer_mult * entry_atr)
                    orders_open = 1

    return True, running_capital

# ==========================================
# 🚀 5. EXECUTE OPTIMIZATION
# ==========================================
keys, values = zip(*PARAM_GRID.items())
permutations = [dict(zip(keys, v)) for v in itertools.product(*values)]
total_tests = len(permutations)

print(f"\n🧪 Starting $500 Personal Account Optimizer...")
print(f"🔄 Testing {total_tests} combinations across 10 years.")
print(f"🎯 Goal: Maximum compound survival starting from $500.")

best_params = None
highest_avg_final_balance = 0.0

for idx, params in enumerate(permutations):
    # Skip illogical parameters where kill switch is tighter than base risk
    if abs(params['LOSS_KILL_SWITCH']) <= params['RISK']:
        continue
        
    if idx % 50 == 0: print(f"⚡ Processing {idx}/{total_tests} grids...")
        
    survived_all = True
    total_final_cap = 0.0
    
    for start_idx in start_indices_arr:
        survived, final_cap = run_personal_simulation(
            float(params['RISK']), float(params['LOSS_KILL_SWITCH']),
            params['TP_MULT'], params['LAYER_MULT'],
            start_idx, date_int_arr, time_hm_arr, open_arr, high_arr, low_arr, 
            close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr
        )
        
        if not survived:
            survived_all = False
            break 
            
        total_final_cap += final_cap
        
    if survived_all:
        avg_cap = total_final_cap / 10.0
        if avg_cap > highest_avg_final_balance:
            highest_avg_final_balance = avg_cap
            best_params = params

if best_params is None:
    print("\n💀 NO PARAMETERS SURVIVED.")
    print("A $500 account using 0.01 lots and 5 layers physically cannot survive Gold's M1 volatility over 10 years. You must either reduce MAX_LAYERS to 2 or 3, or increase starting capital to $1,000.")
else:
    print("\n" + "="*80)
    print("🚀 BEST PARAMETERS FOR $500 PERSONAL ACCOUNT")
    print("="*80)
    print(f"Average 10-Year Final Balance = ${highest_avg_final_balance:,.2f}")
    print("-" * 80)
    print(f"RISK PER TRADE                = ${best_params['RISK']}")
    print(f"FLOATING_LOSS_KILL_SWITCH     = ${best_params['LOSS_KILL_SWITCH']}")
    print(f"TP_MULTIPLIER                 = {best_params['TP_MULT']}x ATR")
    print(f"LAYER_MULTIPLIER (Distance)   = {best_params['LAYER_MULT']}x ATR")
    print("="*80)

mt5.shutdown()
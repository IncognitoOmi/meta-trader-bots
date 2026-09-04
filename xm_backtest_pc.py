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

# # ==========================================
# # 🔬 2. HYPER-COMPOUNDING GRID (%)
# # ==========================================
# PARAM_GRID = {
#     'RISK_PCT': [3.0, 5.0, 8.0, 12.0],            # Aggressive Risk % to force lot sizes up faster
#     'LOSS_KILL_SWITCH_PCT': [25.0, 35.0, 50.0, 65.0], # Massive breathing room for the grid
#     'TP_MULT': [1.0, 1.5, 2.0],                       
#     'LAYER_MULT': [3.0, 4.0, 5.0]             
# }

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()

# # ==========================================
# # 📊 3. FETCH HISTORICAL DATA
# # ==========================================
# print("📥 Fetching 10 years of M1 data...")
# end_date = datetime.now(timezone.utc)
# start_date = end_date - timedelta(days=3650) 

# rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
# if rates is None or len(rates) == 0: 
#     print("❌ No Data Fetched!")
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

# start_indices = []
# for y in range(1, 11):
#     target_date_str = (end_date - timedelta(days=y*365)).strftime('%Y%m%d')
#     idx = np.argmax(date_int_arr >= int(target_date_str))
#     start_indices.append(idx)
# start_indices_arr = np.array(start_indices, dtype=np.int32)

# # ==========================================
# # ⚡ 4. NUMBA C-COMPILED CORE (COMPOUNDING)
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
# def run_dynamic_simulation(risk_pct, loss_pct, tp_mult, layer_mult, start_idx, 
#                            date_arr, time_arr, o_arr, h_arr, l_arr, c_arr, e_arr, r_arr, a_arr, lw_arr, uw_arr):
    
#     running_capital = 500.0  
#     margin_call_level = 50.0 
    
#     active_trade = False
#     direction = 0
#     entry_price = tp = sl = current_lot = 0.0
#     orders_open = 0 
#     layers_prices = np.zeros(5)
    
#     dynamic_kill_switch = 0.0

#     for i in range(max(1, start_idx), len(date_arr)):
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
                
#                 if worst_pnl <= dynamic_kill_switch:
#                     running_capital += dynamic_kill_switch; trade_closed = True
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
                
#                 if worst_pnl <= dynamic_kill_switch:
#                     running_capital += dynamic_kill_switch; trade_closed = True
#                 elif curr_high >= sl:
#                     running_capital += calc_pnl_fast(-1, sl, entry_price, layers_prices, orders_open, current_lot); trade_closed = True
#                 elif curr_low <= tp:
#                     running_capital += calc_pnl_fast(-1, tp, entry_price, layers_prices, orders_open, current_lot); trade_closed = True

#             if trade_closed:
#                 active_trade = False
#                 if running_capital < margin_call_level:
#                     return False, running_capital

#         else:
#             close, ema, rsi, raw_atr = c_arr[i-1], e_arr[i-1], r_arr[i-1], a_arr[i-1]
#             time_hm = time_arr[i]
            
#             if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#                 if close > ema and rsi <= 31 and lw_arr[i-1]:
#                     active_trade, direction = True, 1
#                     adj_atr = raw_atr - 0.5
#                     entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
#                     dynamic_risk_dollar = running_capital * (risk_pct / 100.0)
#                     dynamic_kill_switch = -(running_capital * (loss_pct / 100.0))
                    
#                     c_lot = dynamic_risk_dollar / (42.0 * entry_atr * 100.0)
#                     current_lot = math.floor(c_lot * 100.0) / 100.0
#                     if current_lot < 0.01: current_lot = 0.01 
#                     if current_lot > 50.0: current_lot = 50.0 
                    
#                     entry_price = o_arr[i]
#                     sl, tp = entry_price - (12.0 * entry_atr), entry_price + (tp_mult * entry_atr)
#                     for j in range(1, 6): layers_prices[j-1] = entry_price - (j * layer_mult * entry_atr)
#                     orders_open = 1
                    
#                 elif close < ema and rsi >= 69.8 and uw_arr[i-1]:
#                     active_trade, direction = True, -1
#                     adj_atr = raw_atr - 0.5
#                     entry_atr = 1.5 if adj_atr < 1.5 else round(adj_atr, 2)
                    
#                     dynamic_risk_dollar = running_capital * (risk_pct / 100.0)
#                     dynamic_kill_switch = -(running_capital * (loss_pct / 100.0))
                    
#                     c_lot = dynamic_risk_dollar / (42.0 * entry_atr * 100.0)
#                     current_lot = math.floor(c_lot * 100.0) / 100.0
#                     if current_lot < 0.01: current_lot = 0.01
#                     if current_lot > 50.0: current_lot = 50.0
                    
#                     entry_price = o_arr[i]
#                     sl, tp = entry_price + (12.0 * entry_atr), entry_price - (tp_mult * entry_atr)
#                     for j in range(1, 6): layers_prices[j-1] = entry_price + (j * layer_mult * entry_atr)
#                     orders_open = 1

#     return True, running_capital

# # ==========================================
# # 🚀 5. EXECUTE OPTIMIZATION
# # ==========================================
# keys, values = zip(*PARAM_GRID.items())
# permutations = [dict(zip(keys, v)) for v in itertools.product(*values)]
# total_tests = len(permutations)

# print(f"\n🧪 Starting Hyper-Compounding Optimizer...")
# print(f"🔄 Testing {total_tests} configurations.")

# best_params = None
# highest_avg_final_balance = 0.0

# for idx, params in enumerate(permutations):
#     if params['LOSS_KILL_SWITCH_PCT'] <= params['RISK_PCT']:
#         continue
        
#     if idx % 25 == 0: print(f"⚡ Processing {idx}/{total_tests} grids...")
        
#     survived_all = True
#     total_final_cap = 0.0
    
#     for start_idx in start_indices_arr:
#         survived, final_cap = run_dynamic_simulation(
#             float(params['RISK_PCT']), float(params['LOSS_KILL_SWITCH_PCT']),
#             params['TP_MULT'], params['LAYER_MULT'],
#             start_idx, date_int_arr, time_hm_arr, open_arr, high_arr, low_arr, 
#             close_arr, ema_arr, rsi_arr, atr_arr, lower_wick_arr, upper_wick_arr
#         )
        
#         if not survived:
#             survived_all = False
#             break 
            
#         total_final_cap += final_cap
        
#     if survived_all:
#         avg_cap = total_final_cap / 10.0
#         if avg_cap > highest_avg_final_balance:
#             highest_avg_final_balance = avg_cap
#             best_params = params

# if best_params is None:
#     print("\n💀 NO PARAMETERS SURVIVED.")
# else:
#     print("\n" + "="*80)
#     print("🚀 BEST HYPER-DYNAMIC PARAMETERS FOR $500 ACCOUNT")
#     print("="*80)
#     print(f"Average 10-Year Final Balance = ${highest_avg_final_balance:,.2f} 💰")
#     print("-" * 80)
#     print(f"DYNAMIC RISK PER TRADE        = {best_params['RISK_PCT']}% of Equity")
#     print(f"DYNAMIC LOSS KILL SWITCH      = -{best_params['LOSS_KILL_SWITCH_PCT']}% of Equity")
#     print(f"TP_MULTIPLIER                 = {best_params['TP_MULT']}x ATR")
#     print(f"LAYER_MULTIPLIER (Distance)   = {best_params['LAYER_MULT']}x ATR")
#     print("="*80)

# mt5.shutdown()








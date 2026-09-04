# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import math
# from datetime import datetime, timedelta, timezone
# import pytz

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 720887034 
# account_login = 12219217
# account_password = "1Mz$YuVGJ"
# broker_server = "FundingPips2-SIM"

# # 🚨 PROP FIRM RULES 🚨
# STARTING_CAPITAL = 4702.0  
# PAYOUT_TARGET = 5400.0
# PAYOUT_AMOUNT = 50.0
# MIN_PAYOUT_DAYS = 10

# DAILY_DD_LIMIT = 200.0        # 3% of 50k
# INITIAL_OVERALL_FLOOR = 4500.0 # 4% Max Drawdown
# TRAPDOOR_FLOOR = 5000.0       # Floor after 1st payout

# # STRATEGY RISK RULES
# MAX_RISK = 200.0  
# MIN_SAFE_ATR = 1.5  
# MAX_LAYERS = 5  
# SL_ATR_MULT = MAX_LAYERS * 2  

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()

# # ==========================================
# # 📊 2. FETCH HISTORICAL DATA (365 DAYS)
# # ==========================================
# print("📥 Fetching 365 days of historical data...")
# end_date = datetime.now(timezone.utc)
# start_date = end_date - timedelta(days=365) 

# rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
# if rates is None or len(rates) == 0:
#     print("❌ No Data Fetched!")
#     quit()

# df = pd.DataFrame(rates)

# # 🕒 TIMEZONE FIX
# df['time'] = pd.to_datetime(df['time'], unit='s')
# df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

# df['EMA_280'] = ta.ema(df['close'], length=280)
# df['RSI'] = ta.rsi(df['close'], length=14)
# df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
# df.dropna(inplace=True)
# df.reset_index(drop=True, inplace=True)

# # ==========================================
# # 🧠 3. STRATEGY ENGINE & PROP FIRM TRACKER
# # ==========================================
# tp_hits, sl_hits = 0, 0
# running_capital = STARTING_CAPITAL

# # Prop Firm Tracking Variables
# current_day = None
# start_of_day_balance = STARTING_CAPITAL
# daily_floor = start_of_day_balance - DAILY_DD_LIMIT
# overall_floor = INITIAL_OVERALL_FLOOR
# unique_trading_days = set()
# total_payouts_extracted = 0.0
# payout_count = 0
# account_blown = False
# blown_reason = ""

# active_trade = False
# direction = ""
# entry_price = tp = sl = current_lot = entry_rsi = entry_atr = 0
# orders_open = 0 
# entry_time = None
# layers_prices = []

# def get_fixed_atr(raw_atr):
#     adj = raw_atr - 0.5
#     if adj < MIN_SAFE_ATR:
#         return MIN_SAFE_ATR
#     return round(adj, 2)

# def get_dynamic_lot(fixed_atr):
#     calculated_lot = MAX_RISK / (42 * fixed_atr * 100.0)
#     final_lot = math.floor(calculated_lot * 100) / 100.0
#     return max(0.01, min(final_lot, 10.0))

# def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
#     pnl = 0.0
#     contract = 100.0
#     if dir == "BUY":
#         pnl += (exit_p - e_p) * lot * contract
#         for i in range(total_orders - 1):
#             pnl += (exit_p - l_prices[i]) * lot * contract
#     else:
#         pnl += (e_p - exit_p) * lot * contract
#         for i in range(total_orders - 1):
#             pnl += (l_prices[i] - exit_p) * lot * contract
#     return pnl

# print("\n" + "="*160)
# print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
# print("="*160)

# for i in range(1, len(df)):
#     curr = df.iloc[i]
#     prev = df.iloc[i-1]
    
#     curr_ist_time = curr['time']
#     time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
#     current_date = curr_ist_time.date()
    
#     # 🗓️ DAILY DRAWDOWN RESET LOGIC
#     if current_date != current_day:
#         current_day = current_date
#         start_of_day_balance = running_capital
#         daily_floor = start_of_day_balance - DAILY_DD_LIMIT
    
#     if active_trade:
#         exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
#         entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')
#         trade_closed = False

#         if direction == "BUY":
#             while orders_open < 6 and curr['low'] <= layers_prices[orders_open - 1]:
#                 orders_open += 1
#                 if 2 <= orders_open <= 4:
#                     tp = round(entry_price, 2)
#                 elif orders_open >= 5:
#                     avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
#                     tp = round(avg_entry, 2)
                    
#             if curr['low'] <= sl:
#                 sl_hits += 1
#                 pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#             elif curr['high'] >= tp:
#                 tp_hits += 1
#                 pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#         elif direction == "SELL":
#             while orders_open < 6 and curr['high'] >= layers_prices[orders_open - 1]:
#                 orders_open += 1
#                 if 2 <= orders_open <= 4:
#                     tp = round(entry_price, 2)
#                 elif orders_open >= 5:
#                     avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
#                     tp = round(avg_entry, 2)
                    
#             if curr['high'] >= sl:
#                 sl_hits += 1
#                 pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#             elif curr['low'] <= tp:
#                 tp_hits += 1
#                 pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True

#         # 🚨 PROP FIRM ACCOUNT CHECKS AFTER TRADE CLOSES 🚨
#         if trade_closed:
#             active_trade = False
#             unique_trading_days.add(current_date)
            
#             # 1. DRAWDOWN CHECKS
#             if running_capital < daily_floor:
#                 account_blown = True
#                 blown_reason = f"Daily Drawdown Reached! Dropped below ${daily_floor:.2f}"
#                 break
            
#             if running_capital < overall_floor:
#                 account_blown = True
#                 blown_reason = f"Overall Drawdown Reached! Dropped below ${overall_floor:.2f}"
#                 break
                
#             # 2. PAYOUT CHECKS
#             if running_capital >= PAYOUT_TARGET and len(unique_trading_days) >= MIN_PAYOUT_DAYS:
#                 print("-" * 160)
#                 print(f"🎉 PAYOUT UNLOCKED! Target: ${PAYOUT_TARGET} | Trading Days: {len(unique_trading_days)}")
#                 print(f"💸 Extracting Payout: ${PAYOUT_AMOUNT}")
                
#                 running_capital -= PAYOUT_AMOUNT
#                 total_payouts_extracted += PAYOUT_AMOUNT
#                 payout_count += 1
                
#                 # Activate Trapdoor Floor after 1st payout
#                 overall_floor = TRAPDOOR_FLOOR 
                
#                 # Reset counters for the next payout cycle
#                 unique_trading_days.clear()
#                 start_of_day_balance = running_capital 
#                 daily_floor = start_of_day_balance - DAILY_DD_LIMIT
                
#                 print(f"🛡️ Trapdoor Activated! Overall Floor locked at: ${overall_floor:.2f}")
#                 print(f"🏦 Account Balance after Payout: ${running_capital:.2f}")
#                 print("-" * 160)

#     else:
#         close, ema, rsi, raw_atr = prev['close'], prev['EMA_280'], prev['RSI'], prev['ATR']
#         has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
#         has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
        
#         # 🚨 TIME FILTERS
#         if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#             if close > ema and rsi <= 31 and has_lower_wick:
#                 active_trade = True
#                 direction = "BUY"
#                 entry_atr = get_fixed_atr(raw_atr)
#                 current_lot = get_dynamic_lot(entry_atr)
#                 entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
#                 sl = entry_price - (12 * entry_atr)
#                 tp = entry_price + (2 * entry_atr)
#                 layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, 6)]
#                 orders_open = 1
                
#             elif close < ema and rsi >= 69.8 and has_upper_wick:
#                 active_trade = True
#                 direction = "SELL"
#                 entry_atr = get_fixed_atr(raw_atr)
#                 current_lot = get_dynamic_lot(entry_atr)
#                 entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
#                 sl = entry_price + (12 * entry_atr)
#                 tp = entry_price - (2 * entry_atr)
#                 layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, 6)]
#                 orders_open = 1

# print("="*160)
# print(f"📊 PROP FIRM SIMULATION SUMMARY (365 DAYS)")
# print("="*160)

# if account_blown:
#     print(f"💀 ACCOUNT BLOWN! 💀")
#     print(f"📉 Reason: {blown_reason}")
#     print(f"🏦 Final Balance before blowing: ${running_capital:.2f}")
# else:
#     print(f"🏆 ACCOUNT SURVIVED 1 YEAR! 🏆")
#     print(f"🏦 Final Prop Balance: ${running_capital:.2f}")

# print("-" * 40)
# print(f"✅ Total Wins   : {tp_hits}")
# print(f"❌ Total Losses : {sl_hits}")
# win_rate = (tp_hits/(tp_hits+sl_hits))*100 if (tp_hits+sl_hits) > 0 else 0
# print(f"🎯 Win Rate     : {win_rate:.2f}%")
# print("-" * 40)
# print(f"💸 Total Payouts Reached : {payout_count}")
# print(f"💰 Total Money Extracted : ${total_payouts_extracted:.2f}")
# print("="*160)

# mt5.shutdown()

# =============== Updates script with kill switch

# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import math
# from datetime import datetime, timedelta, timezone
# import pytz

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 720887034 
# account_login = 12219217
# account_password = "1Mz$YuVGJ"
# broker_server = "FundingPips2-SIM"

# # 🚨 PROP FIRM RULES 🚨
# STARTING_CAPITAL = 25000  
# PAYOUT_TARGET = 26000
# PAYOUT_AMOUNT = 250
# MIN_PAYOUT_DAYS = 10

# DAILY_DD_LIMIT = 750        # 3% of 50k (adjust as per exact base)
# INITIAL_OVERALL_FLOOR = 24000 # 4% Max Drawdown
# TRAPDOOR_FLOOR = 25000.0       # Floor after 1st payout

# # STRATEGY RISK RULES
# MAX_RISK = 500.0  
# MAX_FLOATING_LOSS = -250.0    # 🚨 FLOATING LOSS KILL SWITCH 🚨
# MIN_SAFE_ATR = 1.5  
# MAX_LAYERS = 5  
# SL_ATR_MULT = MAX_LAYERS * 2  

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()

# # ==========================================
# # 📊 2. FETCH HISTORICAL DATA (365 DAYS)
# # ==========================================
# print("📥 Fetching 365 days of historical data...")
# end_date = datetime.now(timezone.utc)
# start_date = end_date - timedelta(days=210) 

# rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
# if rates is None or len(rates) == 0:
#     print("❌ No Data Fetched!")
#     quit()

# df = pd.DataFrame(rates)

# # 🕒 TIMEZONE FIX
# df['time'] = pd.to_datetime(df['time'], unit='s')
# df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

# df['EMA_280'] = ta.ema(df['close'], length=285)
# df['RSI'] = ta.rsi(df['close'], length=14)
# df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
# df.dropna(inplace=True)
# df.reset_index(drop=True, inplace=True)

# # ==========================================
# # 🧠 3. STRATEGY ENGINE & PROP FIRM TRACKER
# # ==========================================
# tp_hits, sl_hits = 0, 0
# running_capital = STARTING_CAPITAL

# # Prop Firm Tracking Variables
# current_day = None
# start_of_day_balance = STARTING_CAPITAL
# daily_floor = start_of_day_balance - DAILY_DD_LIMIT
# overall_floor = INITIAL_OVERALL_FLOOR
# unique_trading_days = set()
# total_payouts_extracted = 0.0
# payout_count = 0
# account_blown = False
# blown_reason = ""

# active_trade = False
# direction = ""
# entry_price = tp = sl = current_lot = entry_rsi = entry_atr = 0
# orders_open = 0 
# entry_time = None
# layers_prices = []

# def get_fixed_atr(raw_atr):
#     adj = raw_atr - 0.5
#     if adj < MIN_SAFE_ATR:
#         return MIN_SAFE_ATR
#     return round(adj, 2)

# def get_dynamic_lot(fixed_atr):
#     calculated_lot = MAX_RISK / (42 * fixed_atr * 100.0)
#     final_lot = math.floor(calculated_lot * 100) / 100.0
#     return max(0.01, min(final_lot, 10.0))

# def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
#     pnl = 0.0
#     contract = 100.0
#     if dir == "BUY":
#         pnl += (exit_p - e_p) * lot * contract
#         for i in range(total_orders - 1):
#             pnl += (exit_p - l_prices[i]) * lot * contract
#     else:
#         pnl += (e_p - exit_p) * lot * contract
#         for i in range(total_orders - 1):
#             pnl += (l_prices[i] - exit_p) * lot * contract
#     return pnl

# print("\n" + "="*160)
# print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
# print("="*160)

# for i in range(1, len(df)):
#     curr = df.iloc[i]
#     prev = df.iloc[i-1]
    
#     curr_ist_time = curr['time']
#     time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
#     current_date = curr_ist_time.date()
    
#     # 🗓️ DAILY DRAWDOWN RESET LOGIC
#     if current_date != current_day:
#         current_day = current_date
#         start_of_day_balance = running_capital
#         daily_floor = start_of_day_balance - DAILY_DD_LIMIT
    
#     if active_trade:
#         exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
#         entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')
#         trade_closed = False

#         if direction == "BUY":
#             while orders_open < 6 and curr['low'] <= layers_prices[orders_open - 1]:
#                 orders_open += 1
#                 if 2 <= orders_open <= 4:
#                     tp = round(entry_price, 2)
#                 elif orders_open >= 5:
#                     avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
#                     tp = round(avg_entry, 2)
                    
#             # 🚨 Floating Loss Kill Switch Check
#             worst_floating_pnl = calc_exact_pnl("BUY", curr['low'], entry_price, layers_prices, orders_open, current_lot)
            
#             if worst_floating_pnl <= MAX_FLOATING_LOSS:
#                 sl_hits += 1
#                 running_capital += MAX_FLOATING_LOSS # Cap loss exactly at limit
#                 print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(MAX_FLOATING_LOSS):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True

#             elif curr['low'] <= sl:
#                 sl_hits += 1
#                 pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#             elif curr['high'] >= tp:
#                 tp_hits += 1
#                 pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#         elif direction == "SELL":
#             while orders_open < 6 and curr['high'] >= layers_prices[orders_open - 1]:
#                 orders_open += 1
#                 if 2 <= orders_open <= 4:
#                     tp = round(entry_price, 2)
#                 elif orders_open >= 5:
#                     avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
#                     tp = round(avg_entry, 2)
                    
#             # 🚨 Floating Loss Kill Switch Check
#             worst_floating_pnl = calc_exact_pnl("SELL", curr['high'], entry_price, layers_prices, orders_open, current_lot)
            
#             if worst_floating_pnl <= MAX_FLOATING_LOSS:
#                 sl_hits += 1
#                 running_capital += MAX_FLOATING_LOSS # Cap loss exactly at limit
#                 print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(MAX_FLOATING_LOSS):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True

#             elif curr['high'] >= sl:
#                 sl_hits += 1
#                 pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True
                
#             elif curr['low'] <= tp:
#                 tp_hits += 1
#                 pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
#                 running_capital += pnl
#                 print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
#                 trade_closed = True

#         # 🚨 PROP FIRM ACCOUNT CHECKS AFTER TRADE CLOSES 🚨
#         if trade_closed:
#             active_trade = False
#             unique_trading_days.add(current_date)
            
#             # 1. DRAWDOWN CHECKS
#             if running_capital < daily_floor:
#                 account_blown = True
#                 blown_reason = f"Daily Drawdown Reached! Dropped below ${daily_floor:.2f}"
#                 break
            
#             if running_capital < overall_floor:
#                 account_blown = True
#                 blown_reason = f"Overall Drawdown Reached! Dropped below ${overall_floor:.2f}"
#                 break
                
#             # 2. PAYOUT CHECKS
#             if running_capital >= PAYOUT_TARGET and len(unique_trading_days) >= MIN_PAYOUT_DAYS:
#                 print("-" * 160)
#                 print(f"🎉 PAYOUT UNLOCKED! Target: ${PAYOUT_TARGET} | Trading Days: {len(unique_trading_days)}")
#                 print(f"💸 Extracting Payout: ${PAYOUT_AMOUNT}")
                
#                 running_capital -= PAYOUT_AMOUNT
#                 total_payouts_extracted += PAYOUT_AMOUNT
#                 payout_count += 1
                
#                 # Activate Trapdoor Floor after 1st payout
#                 overall_floor = TRAPDOOR_FLOOR 
                
#                 # Reset counters for the next payout cycle
#                 unique_trading_days.clear()
#                 start_of_day_balance = running_capital 
#                 daily_floor = start_of_day_balance - DAILY_DD_LIMIT
                
#                 print(f"🛡️ Trapdoor Activated! Overall Floor locked at: ${overall_floor:.2f}")
#                 print(f"🏦 Account Balance after Payout: ${running_capital:.2f}")
#                 print("-" * 160)

#     else:
#         close, ema, rsi, raw_atr = prev['close'], prev['EMA_280'], prev['RSI'], prev['ATR']
#         has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
#         has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
        
#         # 🚨 TIME FILTERS
#         if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#             if close > ema and rsi <= 31 and has_lower_wick:
#                 active_trade = True
#                 direction = "BUY"
#                 entry_atr = get_fixed_atr(raw_atr)
#                 current_lot = get_dynamic_lot(entry_atr)
#                 entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
#                 sl = entry_price - (12 * entry_atr)
#                 tp = entry_price + (2 * entry_atr)
#                 layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, 6)]
#                 orders_open = 1
                
#             elif close < ema and rsi >= 69.8 and has_upper_wick:
#                 active_trade = True
#                 direction = "SELL"
#                 entry_atr = get_fixed_atr(raw_atr)
#                 current_lot = get_dynamic_lot(entry_atr)
#                 entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
#                 sl = entry_price + (12 * entry_atr)
#                 tp = entry_price - (2 * entry_atr)
#                 layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, 6)]
#                 orders_open = 1

# print("="*160)
# print(f"📊 PROP FIRM SIMULATION SUMMARY (365 DAYS)")
# print("="*160)

# if account_blown:
#     print(f"💀 ACCOUNT BLOWN! 💀")
#     print(f"📉 Reason: {blown_reason}")
#     print(f"🏦 Final Balance before blowing: ${running_capital:.2f}")
# else:
#     print(f"🏆 ACCOUNT SURVIVED 1 YEAR! 🏆")
#     print(f"🏦 Final Prop Balance: ${running_capital:.2f}")

# print("-" * 40)
# print(f"✅ Total Wins   : {tp_hits}")
# print(f"❌ Total Losses : {sl_hits}")
# win_rate = (tp_hits/(tp_hits+sl_hits))*100 if (tp_hits+sl_hits) > 0 else 0
# print(f"🎯 Win Rate     : {win_rate:.2f}%")
# print("-" * 40)
# print(f"💸 Total Payouts Reached : {payout_count}")
# print(f"💰 Total Money Extracted : ${total_payouts_extracted:.2f}")
# print("="*160)

# mt5.shutdown()


# =============Added post 1st payout risk parameters==========================

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

# 🚨 PROP FIRM RULES 🚨
STARTING_CAPITAL = 25000  
PAYOUT_TARGET = 27500
PAYOUT_AMOUNT = 250
MIN_PAYOUT_DAYS = 10

DAILY_DD_LIMIT = 750        # 3% of 50k (adjust as per exact base)
INITIAL_OVERALL_FLOOR = 24000 # 4% Max Drawdown
TRAPDOOR_FLOOR = 27500.0       # Floor after 1st payout

# STRATEGY RISK RULES (PRE-PAYOUT)
INITIAL_MAX_RISK = 250.0  
INITIAL_MAX_FLOATING_LOSS = -250.0    # 🚨 FLOATING LOSS KILL SWITCH 🚨

# ⚙️ STRATEGY RISK RULES (POST-1ST PAYOUT)
POST_PAYOUT_MAX_RISK = 250.0          # Risk per trade after 1st payout
POST_PAYOUT_MAX_FLOATING_LOSS = -250 # Floating loss limit after 1st payout

MIN_SAFE_ATR = 1.5  
MAX_LAYERS = 5  
SL_ATR_MULT = MAX_LAYERS * 2  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA (365 DAYS)
# ==========================================
print("📥 Fetching 365 days of historical data...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=1095) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)

# 🕒 TIMEZONE FIX
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df['EMA_280'] = ta.ema(df['close'], length=285)
df['RSI'] = ta.rsi(df['close'], length=14)
df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# ==========================================
# 🧠 3. STRATEGY ENGINE & PROP FIRM TRACKER
# ==========================================
tp_hits, sl_hits = 0, 0
running_capital = STARTING_CAPITAL

# Prop Firm Tracking Variables
current_day = None
start_of_day_balance = STARTING_CAPITAL
daily_floor = start_of_day_balance - DAILY_DD_LIMIT
overall_floor = INITIAL_OVERALL_FLOOR
unique_trading_days = set()
total_payouts_extracted = 0.0
payout_count = 0
account_blown = False
blown_reason = ""

# Dynamic Risk Variables
current_max_risk = INITIAL_MAX_RISK
current_max_floating_loss = INITIAL_MAX_FLOATING_LOSS

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

def get_dynamic_lot(fixed_atr, active_max_risk):
    calculated_lot = active_max_risk / (42 * fixed_atr * 100.0)
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

print("\n" + "="*160)
print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<4} | {'ENTRY':<8} | {'EXIT TIME (IST)':<19} | {'EXIT':<8} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL':<10} | {'RUNNING CAP'}")
print("="*160)

for i in range(1, len(df)):
    curr = df.iloc[i]
    prev = df.iloc[i-1]
    
    curr_ist_time = curr['time']
    time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
    current_date = curr_ist_time.date()
    
    # 🗓️ DAILY DRAWDOWN RESET LOGIC
    if current_date != current_day:
        current_day = current_date
        start_of_day_balance = running_capital
        daily_floor = start_of_day_balance - DAILY_DD_LIMIT
    
    if active_trade:
        exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
        entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')
        trade_closed = False

        if direction == "BUY":
            while orders_open < 6 and curr['low'] <= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                    tp = round(avg_entry, 2)
                    
            # 🚨 Floating Loss Kill Switch Check
            worst_floating_pnl = calc_exact_pnl("BUY", curr['low'], entry_price, layers_prices, orders_open, current_lot)
            
            if worst_floating_pnl <= current_max_floating_loss:
                sl_hits += 1
                running_capital += current_max_floating_loss # Cap loss exactly at limit
                print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(current_max_floating_loss):<9.2f} | ${running_capital:.2f}")
                trade_closed = True

            elif curr['low'] <= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
            elif curr['high'] >= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
        elif direction == "SELL":
            while orders_open < 6 and curr['high'] >= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    avg_entry = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                    tp = round(avg_entry, 2)
                    
            # 🚨 Floating Loss Kill Switch Check
            worst_floating_pnl = calc_exact_pnl("SELL", curr['high'], entry_price, layers_prices, orders_open, current_lot)
            
            if worst_floating_pnl <= current_max_floating_loss:
                sl_hits += 1
                running_capital += current_max_floating_loss # Cap loss exactly at limit
                print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | KILL_SW | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(current_max_floating_loss):<9.2f} | ${running_capital:.2f}")
                trade_closed = True

            elif curr['high'] >= sl:
                sl_hits += 1
                pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {sl:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):<9.2f} | ${running_capital:.2f}")
                trade_closed = True
                
            elif curr['low'] <= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
                running_capital += pnl
                print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<4.2f} | {entry_price:<8.2f} | {exit_time_str:<19} | {tp:<8.2f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:<9.2f} | ${running_capital:.2f}")
                trade_closed = True

        # 🚨 PROP FIRM ACCOUNT CHECKS AFTER TRADE CLOSES 🚨
        if trade_closed:
            active_trade = False
            unique_trading_days.add(current_date)
            
            # 1. DRAWDOWN CHECKS
            if running_capital < daily_floor:
                account_blown = True
                blown_reason = f"Daily Drawdown Reached! Dropped below ${daily_floor:.2f}"
                break
            
            if running_capital < overall_floor:
                account_blown = True
                blown_reason = f"Overall Drawdown Reached! Dropped below ${overall_floor:.2f}"
                break
                
            # 2. PAYOUT CHECKS
            if running_capital >= PAYOUT_TARGET and len(unique_trading_days) >= MIN_PAYOUT_DAYS:
                print("-" * 160)
                print(f"🎉 PAYOUT UNLOCKED! Target: ${PAYOUT_TARGET} | Trading Days: {len(unique_trading_days)}")
                print(f"💸 Extracting Payout: ${PAYOUT_AMOUNT}")
                
                running_capital -= PAYOUT_AMOUNT
                total_payouts_extracted += PAYOUT_AMOUNT
                payout_count += 1
                
                # Activate Trapdoor Floor & Adjust Risk after 1st payout
                if payout_count == 1:
                    overall_floor = TRAPDOOR_FLOOR 
                    current_max_risk = POST_PAYOUT_MAX_RISK
                    current_max_floating_loss = POST_PAYOUT_MAX_FLOATING_LOSS
                    print(f"🛡️ Trapdoor Activated! Overall Floor locked at: ${overall_floor:.2f}")
                    print(f"⚙️ MAX RISK LOWERED to ${current_max_risk:.2f} | KILL SWITCH adjusted to ${current_max_floating_loss:.2f}")
                
                # Reset counters for the next payout cycle
                unique_trading_days.clear()
                start_of_day_balance = running_capital 
                daily_floor = start_of_day_balance - DAILY_DD_LIMIT
                
                print(f"🏦 Account Balance after Payout: ${running_capital:.2f}")
                print("-" * 160)

    else:
        close, ema, rsi, raw_atr = prev['close'], prev['EMA_280'], prev['RSI'], prev['ATR']
        has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
        has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
        
        # 🚨 TIME FILTERS
        if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
            if close > ema and rsi <= 31 and has_lower_wick:
                active_trade = True
                direction = "BUY"
                entry_atr = get_fixed_atr(raw_atr)
                current_lot = get_dynamic_lot(entry_atr, current_max_risk)
                entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
                sl = entry_price - (12 * entry_atr)
                tp = entry_price + (2 * entry_atr)
                layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, 6)]
                orders_open = 1
                
            elif close < ema and rsi >= 69.8 and has_upper_wick:
                active_trade = True
                direction = "SELL"
                entry_atr = get_fixed_atr(raw_atr)
                current_lot = get_dynamic_lot(entry_atr, current_max_risk)
                entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                
                sl = entry_price + (12 * entry_atr)
                tp = entry_price - (2 * entry_atr)
                layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, 6)]
                orders_open = 1

print("="*160)
print(f"📊 PROP FIRM SIMULATION SUMMARY (365 DAYS)")
print("="*160)

if account_blown:
    print(f"💀 ACCOUNT BLOWN! 💀")
    print(f"📉 Reason: {blown_reason}")
    print(f"🏦 Final Balance before blowing: ${running_capital:.2f}")
else:
    print(f"🏆 ACCOUNT SURVIVED 1 YEAR! 🏆")
    print(f"🏦 Final Prop Balance: ${running_capital:.2f}")

print("-" * 40)
print(f"✅ Total Wins   : {tp_hits}")
print(f"❌ Total Losses : {sl_hits}")
win_rate = (tp_hits/(tp_hits+sl_hits))*100 if (tp_hits+sl_hits) > 0 else 0
print(f"🎯 Win Rate     : {win_rate:.2f}%")
print("-" * 40)
print(f"💸 Total Payouts Reached : {payout_count}")
print(f"💰 Total Money Extracted : ${total_payouts_extracted:.2f}")
print("="*160)

mt5.shutdown()
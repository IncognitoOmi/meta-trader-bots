# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# import math

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbols = ["XAUUSD"]#"NDX100", "DJI30"]
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 720887034 
# account_login = 12072180
# account_password = "X[<P2r$d6"
# broker_server = "FundingPips2-SIM"

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP2/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ Bot ACTIVE | FundingPips 🦅\n")

# MAX_FLOATING_LOSS = -42.0 # Tera Hard Kill Switch Limit
# MAX_RISK = 140.0 # 🚨 Naya Variable: Tera total grid risk calculation ke liye

# last_trade_time = {sym: 0 for sym in symbols}

# def get_latest_data(symbol):
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=14)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# # 🚨 UPDATED: Indices support added
# def floor_atr(symbol, raw_atr):
#     if symbol == "XAUUSD":
#         adjusted_atr = raw_atr - 0.5
#         if adjusted_atr <= 0:
#             adjusted_atr = 0.1 
#         return round(adjusted_atr, 2)
#     elif symbol in ["NDX100", "DJI30"]:
#         return round(raw_atr, 1)
#     else:
#         return round(raw_atr, 5)

# # 🚨 UPDATED: Math-based Lot Calculation
# def get_dynamic_lot(symbol, raw_atr):
#     fixed_atr = floor_atr(symbol, raw_atr)
    
#     if fixed_atr <= 0: return 0.01
        
#     total_atr_multiplier = 42 
    
#     if symbol == "XAUUSD":
#         contract_size = 100.0
#     elif symbol in ["NDX100", "DJI30"]:
#         contract_size = 1.0
#     else: 
#         contract_size = 100000.0
        
#     calculated_lot = MAX_RISK / (total_atr_multiplier * fixed_atr * contract_size)
    
#     final_lot = math.floor(calculated_lot * 100) / 100.0
    
#     if final_lot < 0.01: return 0.01
#     if final_lot > 5.0: return 5.0 
    
#     return final_lot

# # ==========================================
# # 🛡️ 2. EMERGENCY KILL SWITCH FUNCTION
# # ==========================================
# def emergency_close_all():
#     print("\n🚨 KILL SWITCH TRIGGERED! Closing all live trades and pending limits...")
#     open_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#     if open_pos:
#         for p in open_pos:
#             tick = mt5.symbol_info_tick(p.symbol)
#             if tick is None: continue
#             type_dict = {mt5.POSITION_TYPE_BUY: mt5.ORDER_TYPE_SELL, mt5.POSITION_TYPE_SELL: mt5.ORDER_TYPE_BUY}
#             price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
#             mt5.order_send({
#                 "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol,
#                 "volume": p.volume, "type": type_dict[p.type], "price": price,
#                 "magic": MAGIC_NUMBER, "type_filling": mt5.ORDER_FILLING_IOC,
#             })

#     pending_orders = mt5.orders_get(magic=MAGIC_NUMBER)
#     if pending_orders:
#         for o in pending_orders:
#             mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

# # ==========================================
# # 🔫 3. EXECUTION ENGINE
# # ==========================================
# def execute_grid(symbol, signal_type, raw_atr, current_lot):
#     tick = mt5.symbol_info_tick(symbol)
#     if tick is None: return
#     fixed_atr = floor_atr(symbol, raw_atr)

#     print("\n" + "="*40)
#     print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type} (Confirmed Close)")
#     print(f"📈 ATR: {raw_atr:.5f} | Lot: {current_lot}")
#     print("="*40)

#     entry_p = tick.ask if signal_type == "BUY" else tick.bid
#     tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
#     sl_p = entry_p - (12 * fixed_atr) if signal_type == "BUY" else entry_p + (12 * fixed_atr)
    
#     m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
#     l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
#     mult = -1 if signal_type == "BUY" else 1

#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#         "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
#         "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
#         "type_filling": mt5.ORDER_FILLING_IOC,
#     })

#     for i in range(1, 6):
#         l_price = entry_p + (mult * (i * 2) * fixed_atr) 
#         mt5.order_send({
#             "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
#             "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
#             "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
#         })
#     print(f"🚀 [{symbol}] Grid Placed! All Limits TP set to {entry_p:.5f}")

# # ==========================================
# # 🧠 4. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
        
#         # 🚨 SOFTWARE LOCK: Resets every cycle
#         trade_lock = False 
        
#         global_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#         global_ord = mt5.orders_get(magic=MAGIC_NUMBER)

#         # 🚨 HARD KILL SWITCH CHECK (Every 1 Second)
#         if global_pos:
#             floating_pnl = sum([p.profit + p.swap for p in global_pos])
#             if floating_pnl <= MAX_FLOATING_LOSS:
#                 print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
#                 emergency_close_all()
#                 mt5.shutdown()
#                 quit() 

#         active_pairs = set()
#         if global_pos: active_pairs.update([p.symbol for p in global_pos])
#         if global_ord: active_pairs.update([o.symbol for o in global_ord])
        
#         for symbol in symbols:
#             if trade_lock: 
#                 break 

#             df = get_latest_data(symbol)
#             if df is not None and len(df) > 2:
#                 confirmed_candle = df.iloc[-2] 
#                 running_candle = df.iloc[-1]  
                
#                 close = confirmed_candle['close']
#                 ema = confirmed_candle['EMA_200']
#                 rsi = confirmed_candle['RSI']
#                 raw_atr = confirmed_candle['ATR']
                
#                 c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
#                 has_lower_wick = c_low < c_open and c_low < c_close
#                 has_upper_wick = c_high > c_open and c_high > c_close

#                 open_pos = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)
#                 pending_orders = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
#                 num_pos_actual = len(open_pos) if open_pos else 0
#                 num_pend = len(pending_orders) if pending_orders else 0
                
#                 if num_pos_actual == 0 and num_pend > 0:
#                     print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
#                     for o in pending_orders:
#                         mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                     continue

#                 if num_pos_actual > 0:
#                     base_lot = open_pos[0].volume 
#                     total_vol = sum([p.volume for p in open_pos])
#                     num_pos_effective = round(total_vol / base_lot) 
#                     orig_entry = open_pos[0].price_open
                    
#                     target_tp = None
#                     round_val = 2 if symbol == "XAUUSD" else 5
                    
#                     if 2 <= num_pos_effective <= 4:
#                         target_tp = round(orig_entry, round_val)
#                     elif num_pos_effective >= 5:
#                         average_entry = sum([p.price_open * p.volume for p in open_pos]) / total_vol
#                         target_tp = round(average_entry, round_val)

#                     if target_tp:
#                         for p in open_pos:
#                             if abs(p.tp - target_tp) > 0.00001: 
#                                 mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                     print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live: {running_candle['close']:.5f}       ", end="\r")

#                 elif num_pos_actual == 0 and num_pend == 0:
                    
#                     if len(active_pairs) > 0 and symbol not in active_pairs:
#                         continue 
                        
#                     current_lot = get_dynamic_lot(symbol, raw_atr)
                    
#                     if (current_time - last_trade_time[symbol]) > 60:
#                         if close > ema and rsi <= 31 and has_lower_wick:
#                             execute_grid(symbol, "BUY", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time 
#                             trade_lock = True 
#                             break 
                        
#                         elif close < ema and rsi >= 69.8 and has_upper_wick:
#                             execute_grid(symbol, "SELL", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time
#                             trade_lock = True 
#                             break 

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()

# =====================================================================================================
# =====================================================================================================
# ====================================== Above code has lot sizing wrt max loss===============================================================
# =====================================================================================================
# =====================================================================================================


# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# import math

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbols = ["XAUUSD","EURUSD", "AUDUSD", "GBPUSD"]
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 720887034 
# account_login = 12072180
# account_password = "X[<P2r$d6"
# broker_server = "FundingPips2-SIM"

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP2/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ Bot ACTIVE | FundingPips 🦅\n")

# MAX_FLOATING_LOSS = -42.0 # 

# last_trade_time = {sym: 0 for sym in symbols}

# def get_latest_data(symbol):
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=14)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# def floor_atr(symbol, raw_atr):
#     if symbol == "XAUUSD":
#         adjusted_atr = raw_atr - 0.5
#         if adjusted_atr <= 0:
#             adjusted_atr = 0.1 
#         return round(adjusted_atr, 2)
#     else:
#         return round(raw_atr, 5)

# def get_dynamic_lot(symbol, atr):
#     if symbol in ["EURUSD", "AUDUSD", "GBPUSD"]:
#         if atr <= 0.0001: return 0.25
#         elif 0.0001 < atr <= 0.00015: return 0.20
#         else: return 0.15
#     else:
#         if atr <= 5.0: return 0.02
#         elif 5.0 < atr <= 10.0: return 0.02
#         else: return 0.02

# # ==========================================
# # 🛡️ 2. EMERGENCY KILL SWITCH FUNCTION
# # ==========================================
# def emergency_close_all():
#     print("\n🚨 KILL SWITCH TRIGGERED! Closing all live trades and pending limits...")
#     open_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#     if open_pos:
#         for p in open_pos:
#             tick = mt5.symbol_info_tick(p.symbol)
#             if tick is None: continue
#             type_dict = {mt5.POSITION_TYPE_BUY: mt5.ORDER_TYPE_SELL, mt5.POSITION_TYPE_SELL: mt5.ORDER_TYPE_BUY}
#             price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
#             mt5.order_send({
#                 "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol,
#                 "volume": p.volume, "type": type_dict[p.type], "price": price,
#                 "magic": MAGIC_NUMBER, "type_filling": mt5.ORDER_FILLING_IOC,
#             })

#     pending_orders = mt5.orders_get(magic=MAGIC_NUMBER)
#     if pending_orders:
#         for o in pending_orders:
#             mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

# # ==========================================
# # 🔫 3. EXECUTION ENGINE
# # ==========================================
# def execute_grid(symbol, signal_type, raw_atr, current_lot):
#     tick = mt5.symbol_info_tick(symbol)
#     if tick is None: return
#     fixed_atr = floor_atr(symbol, raw_atr)

#     print("\n" + "="*40)
#     print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type} (Confirmed Close)")
#     print(f"📈 ATR: {raw_atr:.5f} | Lot: {current_lot}")
#     print("="*40)

#     entry_p = tick.ask if signal_type == "BUY" else tick.bid
#     tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
#     sl_p = entry_p - (12 * fixed_atr) if signal_type == "BUY" else entry_p + (12 * fixed_atr)
    
#     m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
#     l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
#     mult = -1 if signal_type == "BUY" else 1

#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#         "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
#         "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
#         "type_filling": mt5.ORDER_FILLING_IOC,
#     })

#     for i in range(1, 6):
#         l_price = entry_p + (mult * (i * 2) * fixed_atr) 
#         mt5.order_send({
#             "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
#             "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
#             "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
#         })
#     print(f"🚀 [{symbol}] Grid Placed! All Limits TP set to {entry_p:.5f}")

# # ==========================================
# # 🧠 4. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
        
#         # 🚨 SOFTWARE LOCK: Resets every cycle
#         trade_lock = False 
        
#         global_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#         global_ord = mt5.orders_get(magic=MAGIC_NUMBER)

#         # 🚨 HARD KILL SWITCH CHECK (Every 1 Second)
#         if global_pos:
#             # Adding profit, swap, and commission to get the EXACT running loss
#             # floating_pnl = sum([p.profit + p.swap + p.commission for p in global_pos])
#             floating_pnl = sum([p.profit + p.swap for p in global_pos])
#             if floating_pnl <= MAX_FLOATING_LOSS:
#                 print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
#                 emergency_close_all()
#                 mt5.shutdown()
#                 quit() # Code permanently stops here to save the account

#         active_pairs = set()
#         if global_pos: active_pairs.update([p.symbol for p in global_pos])
#         if global_ord: active_pairs.update([o.symbol for o in global_ord])
        
#         for symbol in symbols:
#             # 🚨 LATENCY PROTECTION: Skip checking other pairs if a trade just fired in this cycle
#             if trade_lock: 
#                 break 

#             df = get_latest_data(symbol)
#             if df is not None and len(df) > 2:
#                 confirmed_candle = df.iloc[-2] 
#                 running_candle = df.iloc[-1]  
                
#                 close = confirmed_candle['close']
#                 ema = confirmed_candle['EMA_200']
#                 rsi = confirmed_candle['RSI']
#                 raw_atr = confirmed_candle['ATR']
                
#                 c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
#                 has_lower_wick = c_low < c_open and c_low < c_close
#                 has_upper_wick = c_high > c_open and c_high > c_close

#                 open_pos = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)
#                 pending_orders = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
#                 num_pos_actual = len(open_pos) if open_pos else 0
#                 num_pend = len(pending_orders) if pending_orders else 0
                
#                 if num_pos_actual == 0 and num_pend > 0:
#                     print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
#                     for o in pending_orders:
#                         mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                     continue

#                 if num_pos_actual > 0:
#                     base_lot = open_pos[0].volume 
#                     total_vol = sum([p.volume for p in open_pos])
#                     num_pos_effective = round(total_vol / base_lot) 
#                     orig_entry = open_pos[0].price_open
                    
#                     target_tp = None
#                     round_val = 2 if symbol == "XAUUSD" else 5
                    
#                     if 2 <= num_pos_effective <= 4:
#                         target_tp = round(orig_entry, round_val)
#                     elif num_pos_effective >= 5:
#                         average_entry = sum([p.price_open * p.volume for p in open_pos]) / total_vol
#                         target_tp = round(average_entry, round_val)

#                     if target_tp:
#                         for p in open_pos:
#                             if abs(p.tp - target_tp) > 0.00001: 
#                                 mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                     print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live: {running_candle['close']:.5f}       ", end="\r")

#                 elif num_pos_actual == 0 and num_pend == 0:
                    
#                     # 🚨 GLOBAL CHECK: Block new entries if another pair is already active
#                     if len(active_pairs) > 0 and symbol not in active_pairs:
#                         continue 
                        
#                     current_lot = get_dynamic_lot(symbol, raw_atr)
                    
#                     if (current_time - last_trade_time[symbol]) > 60:
#                         if close > ema and rsi <= 31 and has_lower_wick:
#                             execute_grid(symbol, "BUY", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time 
#                             trade_lock = True # 🚨 ACTIVATE LOCK
#                             break 
                        
#                         elif close < ema and rsi >= 69.8 and has_upper_wick:
#                             execute_grid(symbol, "SELL", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time
#                             trade_lock = True # 🚨 ACTIVATE LOCK
#                             break 

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()



##############################
##############################
##############################
import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import math
from datetime import datetime, timedelta
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 720887034 
account_login = 12072180
account_password = "X[<P2r$d6"
broker_server = "FundingPips2-SIM"

# 🚨 TARGET RISK SETTINGS ($45 Max Loss)
MAX_RISK = 45.0  
MAX_FLOATING_LOSS = -45.0 
MIN_SAFE_ATR = 1.5  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP2/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ Bot ACTIVE | Single Pair: {symbol} | 3-Layer Sniper Mode 🦅\n")

last_trade_time = 0

def get_latest_data(symbol):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

def floor_atr(raw_atr):
    adjusted_atr = raw_atr - 0.5
    if adjusted_atr < MIN_SAFE_ATR:
        adjusted_atr = MIN_SAFE_ATR 
    return round(adjusted_atr, 2)

def get_dynamic_lot(raw_atr):
    fixed_atr = floor_atr(raw_atr)
    if fixed_atr <= 0: return 0.01
    
    # 🚨 FIXED MATH: Entry(6 ATR) + L1(4 ATR) + L2(2 ATR) = 12 Total ATR distance
    total_atr_multiplier = 12 
    contract_size = 100.0
    
    calculated_lot = MAX_RISK / (total_atr_multiplier * fixed_atr * contract_size)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    
    if final_lot < 0.01: return 0.01
    if final_lot > 5.0: return 5.0 
    
    return final_lot

# ==========================================
# 🛡️ 2. EMERGENCY KILL SWITCH FUNCTION
# ==========================================
def emergency_close_all():
    print(f"\n🚨 KILL SWITCH TRIGGERED! Closing all live trades and pending limits...")
    open_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
    if open_pos:
        for p in open_pos:
            tick = mt5.symbol_info_tick(p.symbol)
            if tick is None: continue
            type_dict = {mt5.POSITION_TYPE_BUY: mt5.ORDER_TYPE_SELL, mt5.POSITION_TYPE_SELL: mt5.ORDER_TYPE_BUY}
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol,
                "volume": p.volume, "type": type_dict[p.type], "price": price,
                "magic": MAGIC_NUMBER, "type_filling": mt5.ORDER_FILLING_IOC,
            })

    pending_orders = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)
    if pending_orders:
        for o in pending_orders:
            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

# ==========================================
# 🔫 3. EXECUTION ENGINE
# ==========================================
def execute_grid(signal_type, raw_atr, current_lot):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return
    fixed_atr = floor_atr(raw_atr)

    print("\n" + "="*45)
    print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type}")
    print(f"📈 ATR: {raw_atr:.5f} | Safe ATR: {fixed_atr} | Lot: {current_lot}")
    print("="*45)

    entry_p = tick.ask if signal_type == "BUY" else tick.bid
    tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
    # 🚨 FIXED SL: Directly at 6 ATR distance
    sl_p = entry_p - (6 * fixed_atr) if signal_type == "BUY" else entry_p + (6 * fixed_atr)
    
    m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
    l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    mult = -1 if signal_type == "BUY" else 1

    # Main Entry (Layer 0)
    mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
        "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
        "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

    # 🚨 FIXED LAYERS: Sirf 2 Limits lagenge (Layer 1 at 2 ATR, Layer 2 at 4 ATR)
    for i in range(1, 3):
        l_price = entry_p + (mult * (i * 2) * fixed_atr) 
        mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
            "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
            "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
        })
    print(f"🚀 [{symbol}] Grid Placed! 3 Orders max. SL: {sl_p:.2f}")

# ==========================================
# 🧠 4. MAIN LOOP
# ==========================================
try:
    while True:
        current_time = time.time()
        
        # current_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        current_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        time_hm = current_ist.hour * 100 + current_ist.minute
        
        global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
        global_ord = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)

        if global_pos:
            floating_pnl = sum([p.profit + p.swap for p in global_pos])
            if floating_pnl <= MAX_FLOATING_LOSS:
                print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
                emergency_close_all()
                mt5.shutdown()
                quit() 

        df = get_latest_data(symbol)
        if df is not None and len(df) > 2:
            confirmed_candle = df.iloc[-2] 
            running_candle = df.iloc[-1]  
            
            close = confirmed_candle['close']
            ema = confirmed_candle['EMA_200']
            rsi = confirmed_candle['RSI']
            raw_atr = confirmed_candle['ATR']
            
            c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
            has_lower_wick = c_low < c_open and c_low < c_close
            has_upper_wick = c_high > c_open and c_high > c_close

            num_pos_actual = len(global_pos) if global_pos else 0
            num_pend = len(global_ord) if global_ord else 0
            
            if num_pos_actual == 0 and num_pend > 0:
                print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
                for o in global_ord:
                    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                continue

            if num_pos_actual > 0:
                base_lot = global_pos[0].volume 
                total_vol = sum([p.volume for p in global_pos])
                num_pos_effective = round(total_vol / base_lot) 
                orig_entry = global_pos[0].price_open
                
                target_tp = None
                
                # 🚨 FIXED TP LOGIC: Agar 2 ya 3 trades chal rahe hain toh TP entry pe le aao
                if num_pos_effective >= 2:
                    target_tp = round(orig_entry, 2)

                if target_tp:
                    for p in global_pos:
                        if abs(p.tp - target_tp) > 0.00001: 
                            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

                print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live PnL: ${sum([p.profit + p.swap for p in global_pos]):.2f}       ", end="\r")

            elif num_pos_actual == 0 and num_pend == 0:
                
                current_lot = get_dynamic_lot(raw_atr)
                
                if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                    if (current_time - last_trade_time) > 60:
                        if close > ema and rsi <= 31 and has_lower_wick:
                            execute_grid("BUY", raw_atr, current_lot)
                            last_trade_time = current_time 
                            
                        elif close < ema and rsi >= 69.8 and has_upper_wick:
                            execute_grid("SELL", raw_atr, current_lot)
                            last_trade_time = current_time

        time.sleep(1) 
except KeyboardInterrupt:
    mt5.shutdown()
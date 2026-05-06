import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import math

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbols = ["XAUUSD", "EURUSD", "GBPUSD", "AUDUSD"]
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 9833454236 
account_login = 406935
account_password = "BY(aWf92Ri"
broker_server = "BlueGuardian-Server"

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - BlueGuardian/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ Bot ACTIVE | BlueGuardian 🦅\n")

# =====================================================================================================
# =====================================================================================================
# ====================================== LAYER 5 AND 6, TP recalculation Logic Corrected in above code===============================================================
# =====================================================================================================
# =====================================================================================================


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
#         if atr <= 0.0001: return 0.2
#         elif 0.0001 < atr <= 0.00015: return 0.1
#         else: return 0.1
#     else:
#         # XAUUSD Logic
#         if atr <= 5.0: return 0.02
#         elif 5.0 < atr <= 10.0: return 0.02
#         else: return 0.02

# # ==========================================
# # 🔫 2. EXECUTION ENGINE
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
# # 🧠 3. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
        
#         # 🚨 SOFTWARE LOCK: Resets every cycle
#         trade_lock = False 
        
#         global_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#         global_ord = mt5.orders_get(magic=MAGIC_NUMBER)
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
#                         target_tp = round(sum([p.price_open * p.volume for p in open_pos]) / total_vol, round_val)

#                     if target_tp:
#                         for p in open_pos:
#                             if abs(p.tp - target_tp) > 0.00001: 
#                                 mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                     print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live: {running_candle['close']:.5f}      ", end="\r")

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
                        
#                         elif close < ema and rsi >= 69.5 and has_upper_wick:
#                             execute_grid(symbol, "SELL", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time
#                             trade_lock = True # 🚨 ACTIVATE LOCK
#                             break 

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()

# =====================================================================================================
# =====================================================================================================
# ====================================== THIS WAS NOT ABLE TO HANDLE MULTIPLE SIGNAL AT SAME TIME===============================================================
# =====================================================================================================
# =====================================================================================================


# # Har pair ke cooldown ke liye dictionary
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
#         # Forex pairs ke liye zero spread / raw ATR calculation (5 decimal places)
#         return round(raw_atr, 5)

# def get_dynamic_lot(symbol, atr):
#     if symbol in ["EURUSD", "AUDUSD", "GBPUSD"]:
#         if atr <= 0.0001: return 0.2
#         elif 0.0001 < atr <= 0.00015: return 0.1
#         else: return 0.1
#     else:
#         # XAUUSD Logic
#         if atr <= 5.0: return 0.02
#         elif 5.0 < atr <= 10.0: return 0.02
#         else: return 0.02

# # ==========================================
# # 🔫 2. EXECUTION ENGINE
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
# # 🧠 3. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
        
#         for symbol in symbols:
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
#                         target_tp = round(sum([p.price_open * p.volume for p in open_pos]) / total_vol, round_val)

#                     if target_tp:
#                         for p in open_pos:
#                             if abs(p.tp - target_tp) > 0.00001: 
#                                 mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                     print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live: {running_candle['close']:.5f}      ", end="\r")

#                 elif num_pos_actual == 0 and num_pend == 0:
#                     current_lot = get_dynamic_lot(symbol, raw_atr)
                    
#                     # 60 Second cooldown check for individual pair
#                     if (current_time - last_trade_time[symbol]) > 60:
#                         if close > ema and rsi <= 31 and has_lower_wick:
#                             execute_grid(symbol, "BUY", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time 
                        
#                         elif close < ema and rsi >= 69.5 and has_upper_wick:
#                             execute_grid(symbol, "SELL", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()




# # Kill Switch Limit
# DAILY_EXIT_LIMIT = 45.0 

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - BlueGuardian/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ Bot ACTIVE | BlueGuardian 🦅\n")

# # Cooldown timer dict
# last_trade_time = {sym: 0 for sym in symbols}

# # ==========================================
# # 🛡️ 2. EMERGENCY & RISK MANAGEMENT
# # ==========================================
# def emergency_close_all():
#     print("\n🚨 KILL SWITCH TRIGGERED! Closing all trades...")
    
#     # 1. Open Positions Close karo
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

#     # 2. Pending Limit Orders Hatao
#     pending_orders = mt5.orders_get(magic=MAGIC_NUMBER)
#     if pending_orders:
#         for o in pending_orders:
#             mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            
#     print("✅ Sab trades aur pending orders clean ho gaye!")

# # ==========================================
# # 📊 3. DATA & LOGIC FUNCTIONS
# # ==========================================
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
#         adjusted_atr = raw_atr - 0.4
#         if adjusted_atr <= 0:
#             adjusted_atr = 0.1 
#         return round(adjusted_atr, 2)
#     else:
#         # Forex (0 Spread) ke liye jaisa hai waisa (5 decimal)
#         return round(raw_atr, 5)

# def get_dynamic_lot(symbol, atr):
#     if symbol in ["EURUSD", "AUDUSD", "GBPUSD"]:
#         # Forex ke liye fixed 0.1 Lot
#         return 0.10
#     else:
#         # XAUUSD Logic
#         if atr <= 5.0: return 0.01
#         elif 5.0 < atr <= 10.0: return 0.01
#         else: return 0.01

# # ==========================================
# # 🔫 4. EXECUTION ENGINE
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

#     # Market Deal (Base Order)
#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#         "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
#         "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
#         "type_filling": mt5.ORDER_FILLING_IOC,
#     })

#     # Pending Limit Orders (Grid Layers)
#     for i in range(1, 6):
#         l_price = entry_p + (mult * (i * 2) * fixed_atr) 
#         mt5.order_send({
#             "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
#             "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
#             "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
#         })
#     print(f"🚀 [{symbol}] Grid Placed! All Limits TP set to {entry_p:.5f}")

# # ==========================================
# # 🧠 5. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()

#         # --- 🛡️ KILL SWITCH LOGIC CHECK ---
#         today_start = int(time.time() // 86400 * 86400) 
#         history_deals = mt5.history_deals_get(today_start, int(time.time()))
#         realized_pnl = sum([d.profit for d in history_deals if d.magic == MAGIC_NUMBER]) if history_deals else 0.0

#         all_pos = mt5.positions_get(magic=MAGIC_NUMBER)
#         floating_pnl = sum([p.profit + p.swap + p.commission for p in all_pos]) if all_pos else 0.0
        
#         total_pnl = realized_pnl + floating_pnl

#         # Agar limit hit hoti hai toh band kardo
#         if total_pnl <= -DAILY_EXIT_LIMIT or total_pnl >= DAILY_EXIT_LIMIT:
#             print(f"\n⚠️ Daily Limit Reached! Total PnL: ${total_pnl:.2f}")
#             emergency_close_all()
#             mt5.shutdown()
#             quit()
#         # -----------------------------------

#         # Har pair ke liye scanning
#         for symbol in symbols:
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
                
#                 # Cleanup Pending orders if no active trades
#                 if num_pos_actual == 0 and num_pend > 0:
#                     print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
#                     for o in pending_orders:
#                         mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                     continue

#                 # Grid Management & TP Update
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
#                         target_tp = round(sum([p.price_open * p.volume for p in open_pos]) / total_vol, round_val)

#                     if target_tp:
#                         for p in open_pos:
#                             if abs(p.tp - target_tp) > 0.00001: 
#                                 mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                     print(f"[{symbol}] Active Vol: {total_vol:.2f} | Live PnL: ${total_pnl:.2f} 🟢      ", end="\r")

#                 # Strategy Entry Logic
#                 elif num_pos_actual == 0 and num_pend == 0:
#                     current_lot = get_dynamic_lot(symbol, raw_atr)
                    
#                     # 60 Second cooldown check
#                     if (current_time - last_trade_time[symbol]) > 60:
                        
#                         # BUY Signal
#                         if close > ema and rsi <= 31 and has_lower_wick:
#                             execute_grid(symbol, "BUY", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time 
                        
#                         # SELL Signal
#                         elif close < ema and rsi >= 69 and has_upper_wick:
#                             execute_grid(symbol, "SELL", raw_atr, current_lot)
#                             last_trade_time[symbol] = current_time

#         time.sleep(1) # CPU Bachane ke liye
# except KeyboardInterrupt:
#     mt5.shutdown()


# =====================================================================================================
# =====================================================================================================
# ====================================== THIS ONLY INCLUDES XAUUSD===============================================================
# =====================================================================================================
# =====================================================================================================



# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# import math

# # ==========================================
# # ⚙️ SETTINGS
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 9833454236 
# account_login = 406935
# account_password = "BY(aWf92Ri"
# broker_server = "BlueGuardian-Server"

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - BlueGuardian/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ BlueGuardian 🦅\n")

# def get_latest_data():
#     # Hum 250 candles mangwa rahe hain indicators calculation ke liye
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=14)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# # def floor_atr(raw_atr):
# #     return math.floor(raw_atr * 2) / 2
# def floor_atr(raw_atr):
#     # Naya logic: Raw ATR mein se exactly 0.3 minus karega
#     adjusted_atr = raw_atr - 0.4
#     if adjusted_atr <= 0:
#         adjusted_atr = 0.1 
#     return round(adjusted_atr, 2)

# def get_dynamic_lot(atr):
#     if atr <= 5.0: return 0.02
#     elif 5.0 < atr <= 10.0: return 0.01
#     else: return 0.01

# # ==========================================
# # 🔫 2. EXECUTION ENGINE
# # ==========================================
# def execute_grid(signal_type, raw_atr, current_lot):
#     tick = mt5.symbol_info_tick(symbol)
#     if tick is None: return
#     fixed_atr = floor_atr(raw_atr)

#     print("\n" + "="*40)
#     print(f"🔔 EXECUTION TRIGGERED | {signal_type} (Confirmed Close)")
#     print(f"📈 ATR: {raw_atr:.2f} | Lot: {current_lot}")
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
#     print(f"🚀 Grid Placed! All Limits TP set to {entry_p:.2f}")

# # ==========================================
# # 🧠 3. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         df = get_latest_data()
#         if df is not None and len(df) > 2:
#             # 🟢 YAHAN CHANGE HAI: iloc[-2] matlab pichli CLOSED candle
#             confirmed_candle = df.iloc[-2] 
#             running_candle = df.iloc[-1]   # Sirf price update ke liye
            
#             close, ema, rsi, raw_atr = confirmed_candle['close'], confirmed_candle['EMA_200'], confirmed_candle['RSI'], confirmed_candle['ATR']
            
#             # Confirmed Wick Logic (Pichli candle close hone par wick check)
#             c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
#             has_lower_wick = c_low < c_open and c_low < c_close
#             has_upper_wick = c_high > c_open and c_high > c_close

#             open_pos = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)
#             pending_orders = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
#             num_pos_actual = len(open_pos) if open_pos else 0
#             num_pend = len(pending_orders) if pending_orders else 0
            
#             if num_pos_actual == 0 and num_pend > 0:
#                 print("\n🧹 Cleaning up pending orders...")
#                 for o in pending_orders:
#                     mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                 continue

#             if num_pos_actual > 0:
#                 base_lot = open_pos[0].volume 
#                 total_vol = sum([p.volume for p in open_pos])
#                 num_pos_effective = round(total_vol / base_lot) 
#                 orig_entry = open_pos[0].price_open
                
#                 target_tp = None
#                 if 2 <= num_pos_effective <= 4:
#                     target_tp = round(orig_entry, 2)
#                 elif num_pos_effective >= 5:
#                     target_tp = round(sum([p.price_open * p.volume for p in open_pos]) / total_vol, 2)

#                 if target_tp:
#                     for p in open_pos:
#                         if round(p.tp, 2) != target_tp:
#                             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                 print(f"Grid Active... Vol: {total_vol:.2f} | Live Price: {running_candle['close']:.2f}      ", end="\r")

#             elif num_pos_actual == 0 and num_pend == 0:
#                 current_lot = get_dynamic_lot(raw_atr)
#                 print(f"Hunting... RSI(Confirmed): {rsi:.1f} | ATR: {raw_atr:.1f} | Lot: {current_lot}      ", end="\r")
                
#                 # Signal confirmed_candle se check hoga
#                 if close > ema and rsi <= 31 and has_lower_wick:
#                     execute_grid("BUY", raw_atr, current_lot)
#                     time.sleep(61) # Ek minute ke liye pause taaki usi candle pe dubara entry na ho
                
#                 elif close < ema and rsi >= 69.5 and has_upper_wick:
#                     execute_grid("SELL", raw_atr, current_lot)
#                     time.sleep(61)

#         time.sleep(1)
# except KeyboardInterrupt:
#     mt5.shutdown()

############### COMMENTING THE 1:1 PART

# def get_latest_data():
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=14)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# # def floor_atr(raw_atr):
# #     return math.floor(raw_atr * 2) / 2

# def floor_atr(raw_atr):
#     # Naya logic: Raw ATR mein se exactly 0.3 minus karega
#     adjusted_atr = raw_atr - 0.4
#     if adjusted_atr <= 0:
#         adjusted_atr = 0.1 
#     return round(adjusted_atr, 2)


# def get_dynamic_lot(atr):
#     # Strictly Caps Risk at ~$40 per trade based on 2-ATR Stop Loss
#     if atr <= 2.0: return 0.10
#     elif 2.0 < atr <= 3.3: return 0.06
#     elif 3.3 < atr <= 4.0: return 0.05
#     elif 4.0 < atr <= 5.0: return 0.04
#     elif 5.0 < atr <= 6.6: return 0.03
#     elif 6.6 < atr <= 10.0: return 0.02
#     else: return 0.01

# # ==========================================
# # 🧠 MAIN LOOP (1-Shot Sniper Execution)
# # ==========================================
# trade_was_active = False # Status track karne ke liye

# try:
#     while True:
#         df = get_latest_data()
#         if df is not None and len(df) > 2:
#             confirmed_candle = df.iloc[-2] 
#             running_candle = df.iloc[-1]
            
#             close = confirmed_candle['close']
#             ema = confirmed_candle['EMA_200']
#             rsi = confirmed_candle['RSI']
#             raw_atr = confirmed_candle['ATR']
#             fixed_atr = floor_atr(raw_atr)

#             open_pos = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)
#             num_pos = len(open_pos) if open_pos else 0

#             # --- 🛑 TRADE ACTIVE MONITORING ---
#             if num_pos > 0:
#                 trade_was_active = True
#                 current_profit = sum([p.profit for p in open_pos])
#                 print(f"⏳ Trade Active | PnL: ${current_profit:.2f} | Live Price: {running_candle['close']:.2f}      ", end="\r")
#                 time.sleep(1)
#                 continue 

#             # --- 🏁 TRADE CLOSED + 1-MIN DELAY ---
#             if num_pos == 0 and trade_was_active:
#                 print("\n\n" + "🏁"*20)
#                 print(f"💰 TRADE CLOSED! (TP or SL hit). Waiting 60s before next hunt...")
#                 print("🏁"*20 + "\n")
#                 trade_was_active = False # Reset status
#                 time.sleep(60) # 1-minute ka pause
#                 continue

#             # Cleanup leftover pendings
#             pend = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
#             if pend: 
#                 for o in pend: mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

#             # --- 🔫 ENTRY LOGIC (EMA + RSI + SMALL WICK) ---
#             c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
            
#             body_size = abs(c_open - c_close)
#             lower_wick = min(c_open, c_close) - c_low
#             upper_wick = c_high - max(c_open, c_close)
            
#             # ASLI SMALL WICK LOGIC
#             has_small_lower_wick = (lower_wick > 0) and (lower_wick <= body_size)
#             has_small_upper_wick = (upper_wick > 0) and (upper_wick <= body_size)

#             current_lot = get_dynamic_lot(raw_atr)
#             distance = 2 * fixed_atr

#             # 👁️ LIVE HUNTING STATUS
#             print(f"Hunting... RSI: {rsi:.1f} | EMA: {ema:.1f} | ATR-Fix: {fixed_atr:.2f} | Lot: {current_lot}      ", end="\r")

#             # BUY SIGNAL
#             if close > ema and rsi <= 30 and has_small_lower_wick:
#                 tick = mt5.symbol_info_tick(symbol)
#                 sl_p = tick.ask - distance 
#                 tp_p = tick.ask + distance 
                
#                 print("\n\n" + "="*45)
#                 print(f"🚀 SNIPER ENTRY: BUY")
#                 print(f"📍 Entry: {tick.ask:.2f} | SL: {sl_p:.2f} | TP: {tp_p:.2f}")
#                 print(f"📊 ATR: {raw_atr:.2f} | Distance: {distance:.2f} | Lot: {current_lot}")
#                 print("="*45)

#                 mt5.order_send({
#                     "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#                     "type": mt5.ORDER_TYPE_BUY, "price": tick.ask, "sl": round(sl_p, 2), "tp": round(tp_p, 2), 
#                     "magic": MAGIC_NUMBER, "comment": "Sniper_Buy",
#                     "type_filling": mt5.ORDER_FILLING_IOC,
#                 })
#                 time.sleep(61) 

#             # SELL SIGNAL
#             elif close < ema and rsi >= 70 and has_small_upper_wick:
#                 tick = mt5.symbol_info_tick(symbol)
#                 sl_p = tick.bid + distance 
#                 tp_p = tick.bid - distance 
                
#                 print("\n\n" + "="*45)
#                 print(f"🚀 SNIPER ENTRY: SELL")
#                 print(f"📍 Entry: {tick.bid:.2f} | SL: {sl_p:.2f} | TP: {tp_p:.2f}")
#                 print(f"📊 ATR: {raw_atr:.2f} | Distance: {distance:.2f} | Lot: {current_lot}")
#                 print("="*45)

#                 mt5.order_send({
#                     "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#                     "type": mt5.ORDER_TYPE_SELL, "price": tick.bid, "sl": round(sl_p, 2), "tp": round(tp_p, 2), 
#                     "magic": MAGIC_NUMBER, "comment": "Sniper_Sell",
#                     "type_filling": mt5.ORDER_FILLING_IOC,
#                 })
#                 time.sleep(61) 

#         time.sleep(1)
# except KeyboardInterrupt:
#     mt5.shutdown()

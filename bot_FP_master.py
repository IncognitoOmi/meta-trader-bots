# Rules of strategy:
# Indicators: EMA 280, RSI 14, ATR 14.

# Time Filter: 11:30 onwards, strictly avoiding the 17:00 - 18:00 (IST) zone.

# Entry Triggers: RSI extreme (<= 31 for BUY, >= 69.8 for SELL) + respective wick rejection + EMA trend alignment.

# Risk & Position Sizing: Max risk $500, dynamic lot size based on ATR multiplier.

# Trade Management: 6-layer dynamic grid (averaging down at 2x ATR distances), with TP shifting to breakeven or average entry price as layers increase.


# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# import math
# from datetime import datetime, timedelta, timezone

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 983347034 
# account_login = 12219217
# account_password = "1Mz$YuVGJ"
# broker_server = "FundingPips2-SIM"

# # 🚨 TARGET RISK SETTINGS ($45 Max Loss)
# MAX_RISK = 90.0  
# MAX_FLOATING_LOSS = -90.0 
# MIN_SAFE_ATR = 1.5  

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ FP Phase2 MASTER| Single Pair: {symbol} | 2-Layer Sniper Mode 🦅\n")

# last_trade_time = 0

# def get_latest_data(symbol):
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=9)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# def floor_atr(raw_atr):
#     adjusted_atr = raw_atr - 0.2
#     if adjusted_atr < MIN_SAFE_ATR:
#         adjusted_atr = MIN_SAFE_ATR 
#     return round(adjusted_atr, 2)

# def get_dynamic_lot(raw_atr):
#     fixed_atr = floor_atr(raw_atr)
#     if fixed_atr <= 0: return 0.01
    
#     # 🚨 2-LAYER FIXED MATH: Entry(4 ATR SL) + L1(2 ATR SL) = 6 Total ATR distance
#     total_atr_multiplier = 6 
#     contract_size = 100.0
    
#     calculated_lot = MAX_RISK / (total_atr_multiplier * fixed_atr * contract_size)
#     final_lot = math.floor(calculated_lot * 100) / 100.0
    
#     if final_lot < 0.01: return 0.01
#     if final_lot > 5.0: return 5.0 
    
#     return final_lot

# # ==========================================
# # 🛡️ 2. EMERGENCY KILL SWITCH FUNCTION
# # ==========================================
# def emergency_close_all():
#     print(f"\n🚨 KILL SWITCH TRIGGERED! Closing all live trades and pending limits...")
#     open_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
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

#     pending_orders = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)
#     if pending_orders:
#         for o in pending_orders:
#             mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

# # ==========================================
# # 🔫 3. EXECUTION ENGINE
# # ==========================================
# def execute_grid(signal_type, raw_atr, current_lot):
#     tick = mt5.symbol_info_tick(symbol)
#     if tick is None: return
#     fixed_atr = floor_atr(raw_atr)

#     print("\n" + "="*45)
#     print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type}")
#     print(f"📈 ATR: {raw_atr:.5f} | Safe ATR: {fixed_atr} | Lot: {current_lot}")
#     print("="*45)

#     entry_p = tick.ask if signal_type == "BUY" else tick.bid
#     tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
#     # 🚨 FIXED SL: Directly at 4 ATR distance for 2-Layer setup
#     sl_p = entry_p - (4 * fixed_atr) if signal_type == "BUY" else entry_p + (4 * fixed_atr)
    
#     m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
#     l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
#     mult = -1 if signal_type == "BUY" else 1

#     # Main Entry (Layer 0)
#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#         "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
#         "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
#         "type_filling": mt5.ORDER_FILLING_IOC,
#     })

#     # 🚨 FIXED LAYERS: Sirf 1 Limit lagega (Layer 1 at 2 ATR)
#     for i in range(1, 2):
#         l_price = entry_p + (mult * (i * 2) * fixed_atr) 
#         mt5.order_send({
#             "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
#             "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
#             "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
#         })
#     print(f"🚀 [{symbol}] Grid Placed! 2 Orders max. SL: {sl_p:.2f}")

# # ==========================================
# # 🧠 4. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
        
#         current_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
#         time_hm = current_ist.hour * 100 + current_ist.minute
        
#         global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
#         global_ord = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)

#         if global_pos:
#             floating_pnl = sum([p.profit + p.swap for p in global_pos])
#             if floating_pnl <= MAX_FLOATING_LOSS:
#                 print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
#                 emergency_close_all()
#                 mt5.shutdown()
#                 quit() 

#         df = get_latest_data(symbol)
#         if df is not None and len(df) > 2:
#             confirmed_candle = df.iloc[-2] 
#             running_candle = df.iloc[-1]  
            
#             close = confirmed_candle['close']
#             ema = confirmed_candle['EMA_200']
#             rsi = confirmed_candle['RSI']
#             raw_atr = confirmed_candle['ATR']
            
#             c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
#             has_lower_wick = c_low < c_open and c_low < c_close
#             has_upper_wick = c_high > c_open and c_high > c_close

#             num_pos_actual = len(global_pos) if global_pos else 0
#             num_pend = len(global_ord) if global_ord else 0
            
#             if num_pos_actual == 0 and num_pend > 0:
#                 print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
#                 for o in global_ord:
#                     mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                 continue

#             if num_pos_actual > 0:
#                 base_lot = global_pos[0].volume 
#                 total_vol = sum([p.volume for p in global_pos])
#                 num_pos_effective = round(total_vol / base_lot) 
#                 orig_entry = global_pos[0].price_open
                
#                 target_tp = None
                
#                 # 🚨 FIXED TP LOGIC: Agar 2 trades chal rahe hain toh TP entry pe le aao
#                 if num_pos_effective >= 2:
#                     target_tp = round(orig_entry, 2)

#                 if target_tp:
#                     for p in global_pos:
#                         if abs(p.tp - target_tp) > 0.00001: 
#                             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                 print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live PnL: ${sum([p.profit + p.swap for p in global_pos]):.2f}       ", end="\r")

#             elif num_pos_actual == 0 and num_pend == 0:
                
#                 current_lot = get_dynamic_lot(raw_atr)
                
#                 if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#                     if (current_time - last_trade_time) > 60:
#                         if close > ema and rsi <= 31 and has_lower_wick:
#                             execute_grid("BUY", raw_atr, current_lot)
#                             last_trade_time = current_time 
                            
#                         elif close < ema and rsi >= 69.8 and has_upper_wick:
#                             execute_grid("SELL", raw_atr, current_lot)
#                             last_trade_time = current_time

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()


# import MetaTrader5 as mt5
# import pandas as pd
# import pandas_ta as ta
# import time
# import math
# from datetime import datetime, timedelta, timezone

# # ==========================================
# # ⚙️ 1. SETTINGS & LOGIN
# # ==========================================
# symbol = "XAUUSD"
# timeframe = mt5.TIMEFRAME_M1
# MAGIC_NUMBER = 983347034 
# account_login = 12219217
# account_password = "1Mz$YuVGJ"
# broker_server = "FundingPips2-SIM"

# # 🚨 TARGET RISK SETTINGS ($45 Max Loss)
# MAX_RISK = 90.0  
# MAX_FLOATING_LOSS = -90.0 
# MIN_SAFE_ATR = 1.5  

# if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
#     print("❌ MT5 Connection Fail!")
#     quit()
# print(f"✅ FP Phase2 MASTER| Single Pair: {symbol} | 2-Layer Sniper Mode 🦅\n")

# last_trade_time = 0

# def get_latest_data(symbol):
#     rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)
#     if rates is None: return None
#     df = pd.DataFrame(rates)
#     df['EMA_200'] = ta.ema(df['close'], length=200)
#     df['RSI'] = ta.rsi(df['close'], length=9)
#     df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
#     return df

# def floor_atr(raw_atr):
#     adjusted_atr = raw_atr - 0.2
#     return round(max(adjusted_atr, MIN_SAFE_ATR), 2)

# def get_dynamic_lot(raw_atr):
#     fixed_atr = floor_atr(raw_atr)
#     if fixed_atr <= 0: return 0.01
    
#     total_atr_multiplier = 6 
#     contract_size = 100.0
    
#     calculated_lot = MAX_RISK / (total_atr_multiplier * fixed_atr * contract_size)
#     final_lot = math.floor(calculated_lot * 100) / 100.0
    
#     return max(0.01, min(final_lot, 5.0))

# # ==========================================
# # 🛡️ 2. EMERGENCY KILL SWITCH FUNCTION
# # ==========================================
# def emergency_close_all():
#     print(f"\n🚨 KILL SWITCH TRIGGERED! Closing all live trades and pending limits...")
#     open_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
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

#     pending_orders = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)
#     if pending_orders:
#         for o in pending_orders:
#             mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

# # ==========================================
# # 🔫 3. EXECUTION ENGINE
# # ==========================================
# def execute_grid(signal_type, raw_atr, current_lot, ema_val, rsi_val):
#     tick = mt5.symbol_info_tick(symbol)
#     if tick is None: return
#     fixed_atr = floor_atr(raw_atr)
#     entry_p = tick.ask if signal_type == "BUY" else tick.bid

#     print("\n" + "="*50)
#     print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type}")
#     print(f"🎯 Entry Price: {entry_p:.2f} | EMA: {ema_val:.2f} | RSI: {rsi_val:.2f}")
#     print(f"📈 ATR: {raw_atr:.5f} | Safe ATR: {fixed_atr} | Lot: {current_lot}")
#     print("="*50)

#     tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
#     sl_p = entry_p - (4 * fixed_atr) if signal_type == "BUY" else entry_p + (4 * fixed_atr)
    
#     m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
#     l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
#     mult = -1 if signal_type == "BUY" else 1

#     # Main Entry
#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
#         "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
#         "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
#         "type_filling": mt5.ORDER_FILLING_IOC,
#     })

#     # Limit Order Layer
#     l_price = entry_p + (mult * 2 * fixed_atr) 
#     mt5.order_send({
#         "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
#         "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
#         "magic": MAGIC_NUMBER, "comment": "Layer 1",
#     })
#     print(f"🚀 [{symbol}] Grid Placed! 2 Orders max. SL: {sl_p:.2f}")

# # ==========================================
# # 🧠 4. MAIN LOOP
# # ==========================================
# try:
#     while True:
#         current_time = time.time()
#         current_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
#         time_hm = current_ist.hour * 100 + current_ist.minute
        
#         global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
#         global_ord = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)

#         # Drawdown Check
#         if global_pos:
#             floating_pnl = sum([p.profit + p.swap for p in global_pos])
#             if floating_pnl <= MAX_FLOATING_LOSS:
#                 print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
#                 emergency_close_all()
#                 mt5.shutdown()
#                 quit() 

#         df = get_latest_data(symbol)
#         if df is not None and len(df) > 2:
#             confirmed_candle = df.iloc[-2] 
            
#             close = confirmed_candle['close']
#             ema = confirmed_candle['EMA_200']
#             rsi = confirmed_candle['RSI']
#             raw_atr = confirmed_candle['ATR']
            
#             c_open, c_high, c_low = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low']
#             has_lower_wick = c_low < c_open and c_low < close
#             has_upper_wick = c_high > c_open and c_high > close

#             num_pos_actual = len(global_pos) if global_pos else 0
#             num_pend = len(global_ord) if global_ord else 0
            
#             # Cleanup stray pending orders
#             if num_pos_actual == 0 and num_pend > 0:
#                 print(f"\n🧹 [{symbol}] Cleaning up pending orders...")
#                 for o in global_ord:
#                     mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
#                 continue

#             # TP Management
#             if num_pos_actual > 0:
#                 base_lot = global_pos[0].volume 
#                 total_vol = sum([p.volume for p in global_pos])
#                 num_pos_effective = round(total_vol / base_lot) 
#                 orig_entry = global_pos[0].price_open
                
#                 target_tp = round(orig_entry, 2) if num_pos_effective >= 2 else None

#                 if target_tp:
#                     for p in global_pos:
#                         if abs(p.tp - target_tp) > 0.00001: 
#                             mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

#                 print(f"[{symbol}] Grid Active | Vol: {total_vol:.2f} | Live PnL: ${sum([p.profit + p.swap for p in global_pos]):.2f}       ", end="\r")

#             # Entry Logic
#             elif num_pos_actual == 0 and num_pend == 0:
#                 current_lot = get_dynamic_lot(raw_atr)
                
#                 if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
#                     if (current_time - last_trade_time) > 60:
                        
#                         # BUY CONDITION
#                         if close > ema and rsi <= 30 and has_lower_wick:
#                             execute_grid("BUY", raw_atr, current_lot, ema, rsi)
#                             last_trade_time = current_time 
                            
#                         # SELL CONDITION
#                         elif close < ema and rsi >= 70 and has_upper_wick:
#                             execute_grid("SELL", raw_atr, current_lot, ema, rsi)
#                             last_trade_time = current_time

#         time.sleep(1) 
# except KeyboardInterrupt:
#     mt5.shutdown()



# ======================

import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import math
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 720887034 
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"

# 🚨 TARGET RISK SETTINGS
MAX_RISK = 200.0  
MAX_FLOATING_LOSS = -150.0  # Strict exit PnL
MIN_SAFE_ATR = 1.5  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ FP MASTER BOT | Symbol: {symbol} | 6-Layer Grid Mode Active 🦅\n")

last_processed_candle_time = None

# ==========================================
# 📊 2. DATA & CALCULATION FUNCTIONS
# ==========================================
def get_latest_data(symbol):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['EMA_280'] = ta.ema(df['close'], length=285)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

def get_fixed_atr(raw_atr):
    adj = raw_atr - 0.5
    if adj < MIN_SAFE_ATR:
        return MIN_SAFE_ATR
    return round(adj, 2)

def get_dynamic_lot(fixed_atr):
    calculated_lot = MAX_RISK / (42 * fixed_atr * 100.0)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    return max(0.01, min(final_lot, 10.0))

# ==========================================
# 🛡️ 3. EMERGENCY KILL SWITCH FUNCTION
# ==========================================
def emergency_close_all():
    print(f"\n🚨 KILL SWITCH TRIGGERED! Max Loss Reached. Closing all live trades and limits...")
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
# 🔫 4. EXECUTION ENGINE (6-LAYER GRID)
# ==========================================
def execute_grid(signal_type, raw_atr, current_lot, entry_price):
    fixed_atr = get_fixed_atr(raw_atr)
    
    print("\n" + "="*60)
    print(f"🔔 [{symbol}] EXECUTION TRIGGERED | {signal_type}")
    print(f"🎯 Entry Price: {entry_price:.2f} | Safe ATR: {fixed_atr} | Lot: {current_lot}")
    print("="*60)

    # Calculate SL and Initial TP
    tp_dist = 2 * fixed_atr
    sl_dist = 12 * fixed_atr

    if signal_type == "BUY":
        tp_0atr = entry_price + tp_dist
        sl_p = entry_price - sl_dist
        m_type = mt5.ORDER_TYPE_BUY
        l_type = mt5.ORDER_TYPE_BUY_LIMIT
        mult = -1
    else:
        tp_0atr = entry_price - tp_dist
        sl_p = entry_price + sl_dist
        m_type = mt5.ORDER_TYPE_SELL
        l_type = mt5.ORDER_TYPE_SELL_LIMIT
        mult = 1

    # 1. Place Main Market Entry
    mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
        "type": m_type, "price": entry_price, "sl": sl_p, "tp": tp_0atr, 
        "magic": MAGIC_NUMBER, "comment": f"Mkt Layer 1",
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

    # 2. Place 5 Pending Limit Layers
    for i in range(1, 6):
        l_price = entry_price + (mult * i * 2 * fixed_atr)
        mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
            "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_price, 
            "magic": MAGIC_NUMBER, "comment": f"Limit Layer {i+1}",
        })
    print(f"🚀 [{symbol}] Grid Placed! 1 Market + 5 Limits. Exact SL: {sl_p:.2f}")

# ==========================================
# 🧠 5. MAIN LIVE LOOP
# ==========================================
try:
    while True:
        current_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        time_hm = current_ist.hour * 100 + current_ist.minute
        
        global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
        global_ord = mt5.orders_get(magic=MAGIC_NUMBER, symbol=symbol)

        # 🚨 KILL SWITCH: Drawdown Check
        if global_pos:
            floating_pnl = sum([p.profit + p.swap for p in global_pos])
            if floating_pnl <= MAX_FLOATING_LOSS:
                print(f"\n⚠️ DANGER: Loss limit hit! Current PnL: ${floating_pnl:.2f}")
                emergency_close_all()
                continue 

        df = get_latest_data(symbol)
        if df is not None and len(df) > 2:
            
            current_candle = df.iloc[-1]
            prev_candle = df.iloc[-2] # The candle that just closed
            
            num_pos_actual = len(global_pos) if global_pos else 0
            num_pend = len(global_ord) if global_ord else 0
            
            # 🧹 CLEANUP: If all positions closed (TP/SL hit) but pending limits remain
            if num_pos_actual == 0 and num_pend > 0:
                print(f"\n🧹 [{symbol}] Trade finished. Cleaning up remaining limit orders...")
                for o in global_ord:
                    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                continue

            # 🎯 DYNAMIC TP MANAGER: Update TPs if grid layers get activated
            if num_pos_actual > 0:
                sorted_pos = sorted(global_pos, key=lambda x: x.time)
                base_entry = sorted_pos[0].price_open
                
                total_vol = sum([p.volume for p in global_pos])
                avg_entry = sum([p.price_open * p.volume for p in global_pos]) / total_vol
                
                target_tp = None
                if 2 <= num_pos_actual <= 4:
                    target_tp = round(base_entry, 2)
                elif num_pos_actual >= 5:
                    target_tp = round(avg_entry, 2)

                if target_tp:
                    for p in global_pos:
                        if abs(p.tp - target_tp) > 0.01: 
                            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

                print(f"[{symbol}] Grid Active | Layers Open: {num_pos_actual} | Live PnL: ${sum([p.profit + p.swap for p in global_pos]):.2f}       ", end="\r")

            # 🏹 ENTRY LOGIC: Only check once per new candle close
            elif num_pos_actual == 0 and num_pend == 0:
                if last_processed_candle_time != current_candle['time']:
                    
                    # 🕒 TIME FILTERS
                    if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                        
                        # Fetch Data from the candle that just closed
                        close, ema, rsi, raw_atr = prev_candle['close'], prev_candle['EMA_280'], prev_candle['RSI'], prev_candle['ATR']
                        has_lower_wick = prev_candle['low'] < prev_candle['open'] and prev_candle['low'] < prev_candle['close']
                        has_upper_wick = prev_candle['high'] > prev_candle['open'] and prev_candle['high'] > prev_candle['close']

                        current_lot = get_dynamic_lot(get_fixed_atr(raw_atr))
                        tick = mt5.symbol_info_tick(symbol)
                        
                        if tick is not None:
                            # 📈 BUY CONDITION
                            if close > ema and rsi <= 31 and has_lower_wick:
                                execute_grid("BUY", raw_atr, current_lot, tick.ask)
                            
                            # 📉 SELL CONDITION
                            elif close < ema and rsi >= 69.8 and has_upper_wick:
                                execute_grid("SELL", raw_atr, current_lot, tick.bid)
                    
                    # Mark candle as processed so we don't spam evaluate it
                    last_processed_candle_time = current_candle['time']

        time.sleep(0.5) 
except KeyboardInterrupt:
    print("\n🛑 Bot Stopped by User.")
    mt5.shutdown()
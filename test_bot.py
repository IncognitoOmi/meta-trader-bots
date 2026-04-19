import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time

# ==========================================
# ⚙️ BHAi KI DEMO DETAILS & SETTINGS
# ==========================================
account_login = 104839652
account_password = "SvY@0aAv"
broker_server = "MetaQuotes-Demo"
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
LOT_SIZE = 0.03
MAGIC_NUMBER = 999999

# ==========================================
# 🔌 1. CONNECTION SETUP
# ==========================================
print("MT5 Engine start kar raha hu...")
if not mt5.initialize() or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print("✅ Connection SUCCESSFUL! Bot zinda ho gaya hai... 🦅\n")

# ==========================================
# 👁️ 2. DATA ENGINE
# ==========================================
def get_latest_data():
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 250)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.atr(length=14, append=True)
    return df.iloc[-1]

# ==========================================
# 🔫 3. EXECUTION ENGINE (0 ATR Entry + 2x ATR Grid)
# ==========================================
def execute_grid(signal_type, atr):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return

    TP_DISTANCE = 2 * atr  # Pehle order ka target 2 ATR
    SL_DISTANCE = 12 * atr # Hard SL 12 ATR par (Tujhe yeda na lage isliye fix kar diya 😂)

    if signal_type == "BUY":
        entry_price = tick.ask
        tp_price = entry_price + TP_DISTANCE
        sl_price = entry_price - SL_DISTANCE  
        market_type = mt5.ORDER_TYPE_BUY
        limit_type = mt5.ORDER_TYPE_BUY_LIMIT
        multiplier = -1 
    elif signal_type == "SELL":
        entry_price = tick.bid
        tp_price = entry_price - TP_DISTANCE
        sl_price = entry_price + SL_DISTANCE  
        market_type = mt5.ORDER_TYPE_SELL
        limit_type = mt5.ORDER_TYPE_SELL_LIMIT
        multiplier = 1   

    # --- 1. MARKET ORDER (WITH TP & SL) ---
    market_req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": LOT_SIZE,
        "type": market_type, "price": entry_price, "sl": sl_price, "tp": tp_price, 
        "deviation": 20, "magic": MAGIC_NUMBER, "comment": "Omkar 0 ATR",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
    }
    mt5.order_send(market_req)
    print(f"✅ 0 ATR {signal_type} Placed! Entry: {entry_price:.2f} | TP: {tp_price:.2f} | SL: {sl_price:.2f}")

    # --- 2. LIMIT ORDERS (At 2, 4, 6, 8, 10 ATR Gap) ---
    for i in range(1, 6):
        limit_price = entry_price + (multiplier * (i * 2) * atr) 
        limit_req = {
            "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": LOT_SIZE,
            "type": limit_type, "price": limit_price, "sl": sl_price, "tp": 0.0, 
            "deviation": 20, "magic": MAGIC_NUMBER, "comment": f"Omkar Layer {i}",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(limit_req)
        print(f"   ⏳ Layer {i} Limit Set at {limit_price:.2f}")

# ==========================================
# 🧠 4. THE MAIN LOOP (Exit Manager + Test Trigger)
# ==========================================
try:
    while True:
        latest = get_latest_data()
        if latest is not None:
            close = latest['close']
            atr = latest['ATRr_14']
            
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions is None: continue 
            num_positions = len(open_positions)
            
            # --------------------------------------------------
            # SCENARIO A: Trades chal rahe hain (THE EXIT MANAGER)
            # --------------------------------------------------
            if num_positions > 0:
                # 1. Sabka Average Price Calculate karo
                total_volume = sum([pos.volume for pos in open_positions])
                weighted_price = sum([(pos.price_open * pos.volume) for pos in open_positions])
                average_entry_price = weighted_price / total_volume
                
                print(f"[{num_positions} Active Trade(s)] Avg Price: {average_entry_price:.2f} | Live Price: {close:.2f}   ", end="\r")
                
                # 2. Agar 1 se zyada trades active ho gaye (Layer 1+ triggered)
                if num_positions > 1:
                    new_tp = average_entry_price # Break-even TP
                    
                    for pos in open_positions:
                        # Sirf tab modify karo jab TP already average price par na ho (Spam bachane ke liye)
                        if round(pos.tp, 2) != round(new_tp, 2):
                            modify_req = {
                                "action": mt5.TRADE_ACTION_SLTP, "position": pos.ticket,
                                "symbol": symbol, "sl": pos.sl, "tp": new_tp
                            }
                            res = mt5.order_send(modify_req)
                            if res.retcode == mt5.TRADE_RETCODE_DONE:
                                print(f"\n🔄 Magic! Ticket {pos.ticket} ka TP modify karke {new_tp:.2f} (Average) kar diya!")

            # --------------------------------------------------
            # SCENARIO B: Market khali hai (TESTING TRIGGER)
            # --------------------------------------------------
            else:
                print(f"\n🚨 TEST MODE: Forcing BUY execution immediately! ATR = {atr:.2f}")
                execute_grid("BUY", atr)
                print("\n✅ Orders Sent! Ab hum Dynamic TP test karenge...\n")
                time.sleep(5) 
                
        time.sleep(2) 

except KeyboardInterrupt:
    print("\n\n⏹️ Bot stopped.")
    mt5.shutdown()
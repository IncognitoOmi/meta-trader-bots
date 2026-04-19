import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import math

# ==========================================
# ⚙️ SETTINGS
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 9833454236 
account_login = 406935
# account_password = "T)72+?sV6"
# broker_server = "FundingPips2-SIM"

account_password = "BY(aWf92Ri"
broker_server = "BlueGuardian-Server"

if not mt5.initialize(path = "C:/Program Files/MetaTrader 5 - BG/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ Bot ACTIVE 🦅 | Waiting for Candle Close Logic ON\n")

def get_latest_data():
    # Hum 250 candles mangwa rahe hain indicators calculation ke liye
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 250)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

def floor_atr(raw_atr):
    return math.floor(raw_atr * 2) / 2

def get_dynamic_lot(atr):
    if atr <= 5.0: return 0.03
    elif 5.0 < atr <= 10.0: return 0.02
    else: return 0.01

# ==========================================
# 🔫 2. EXECUTION ENGINE
# ==========================================
def execute_grid(signal_type, raw_atr, current_lot):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return
    fixed_atr = floor_atr(raw_atr)

    print("\n" + "="*40)
    print(f"🔔 EXECUTION TRIGGERED | {signal_type} (Confirmed Close)")
    print(f"📈 ATR: {raw_atr:.2f} | Lot: {current_lot}")
    print("="*40)

    entry_p = tick.ask if signal_type == "BUY" else tick.bid
    tp_0atr = entry_p + (2 * fixed_atr) if signal_type == "BUY" else entry_p - (2 * fixed_atr)
    sl_p = entry_p - (12 * fixed_atr) if signal_type == "BUY" else entry_p + (12 * fixed_atr)
    
    m_type = mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL
    l_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    mult = -1 if signal_type == "BUY" else 1

    mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": current_lot,
        "type": m_type, "price": entry_p, "sl": sl_p, "tp": tp_0atr, 
        "magic": MAGIC_NUMBER, "comment": f"ATR:{fixed_atr}",
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

    for i in range(1, 6):
        l_price = entry_p + (mult * (i * 2) * fixed_atr) 
        mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING, "symbol": symbol, "volume": current_lot,
            "type": l_type, "price": l_price, "sl": sl_p, "tp": entry_p, 
            "magic": MAGIC_NUMBER, "comment": f"Layer {i}",
        })
    print(f"🚀 Grid Placed! All Limits TP set to {entry_p:.2f}")

# ==========================================
# 🧠 3. MAIN LOOP
# ==========================================
try:
    while True:
        df = get_latest_data()
        if df is not None and len(df) > 2:
            # 🟢 YAHAN CHANGE HAI: iloc[-2] matlab pichli CLOSED candle
            confirmed_candle = df.iloc[-2] 
            running_candle = df.iloc[-1]   # Sirf price update ke liye
            
            close, ema, rsi, raw_atr = confirmed_candle['close'], confirmed_candle['EMA_200'], confirmed_candle['RSI'], confirmed_candle['ATR']
            
            # Confirmed Wick Logic (Pichli candle close hone par wick check)
            c_open, c_high, c_low, c_close = confirmed_candle['open'], confirmed_candle['high'], confirmed_candle['low'], confirmed_candle['close']
            has_lower_wick = c_low < c_open and c_low < c_close
            has_upper_wick = c_high > c_open and c_high > c_close

            open_pos = mt5.positions_get(symbol=symbol, magic=MAGIC_NUMBER)
            pending_orders = mt5.orders_get(symbol=symbol, magic=MAGIC_NUMBER)
            num_pos_actual = len(open_pos) if open_pos else 0
            num_pend = len(pending_orders) if pending_orders else 0
            
            if num_pos_actual == 0 and num_pend > 0:
                print("\n🧹 Cleaning up pending orders...")
                for o in pending_orders:
                    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                continue

            if num_pos_actual > 0:
                base_lot = open_pos[0].volume 
                total_vol = sum([p.volume for p in open_pos])
                num_pos_effective = round(total_vol / base_lot) 
                orig_entry = open_pos[0].price_open
                
                target_tp = None
                if 2 <= num_pos_effective <= 4:
                    target_tp = round(orig_entry, 2)
                elif num_pos_effective >= 5:
                    target_tp = round(sum([p.price_open * p.volume for p in open_pos]) / total_vol, 2)

                if target_tp:
                    for p in open_pos:
                        if round(p.tp, 2) != target_tp:
                            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": p.sl, "tp": target_tp})

                print(f"Grid Active... Vol: {total_vol:.2f} | Live Price: {running_candle['close']:.2f}      ", end="\r")

            elif num_pos_actual == 0 and num_pend == 0:
                current_lot = get_dynamic_lot(raw_atr)
                print(f"Hunting... RSI(Confirmed): {rsi:.1f} | ATR: {raw_atr:.1f} | Lot: {current_lot}      ", end="\r")
                
                # Signal confirmed_candle se check hoga
                if close > ema and rsi <= 30 and has_lower_wick:
                    execute_grid("BUY", raw_atr, current_lot)
                    time.sleep(61) # Ek minute ke liye pause taaki usi candle pe dubara entry na ho
                
                elif close < ema and rsi >= 70 and has_upper_wick:
                    execute_grid("SELL", raw_atr, current_lot)
                    time.sleep(61)

        time.sleep(1)
except KeyboardInterrupt:
    mt5.shutdown()
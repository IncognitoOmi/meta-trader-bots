import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
import math
from datetime import datetime, timedelta, timezone
import pytz

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN (5K MASTER ACCOUNT)
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 720887034 
account_login = 20636704
account_password = "hnV3qs0%T"
broker_server = "FundingPips-SIM1"
mt5_path = r"C:\Program Files\MetaTrader 5 - FP1-5k\terminal64.exe"

# 🚨 STRATEGY RISK RULES
RISK_PER_TRADE = 30.0        # $30 per trade
MAX_DAILY_LOSS = -45.0      # Daily emergency kill switch (Buffer below $150 limit)

# 🔥 SMC SETTINGS
SL_BUFFER = 0.50             # $0.50 (5 pips) below/above sweep wick
RR_MULTIPLIER = 1.0          # 1:1 Risk Reward
MAX_PATTERN_CANDLES = 90     # Exact match with backtesting

# ==========================================
# 🔌 2. MT5 INITIALIZATION
# ==========================================
if not mt5.initialize(path=mt5_path) or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ SMC LIVE BOT | Symbol: {symbol} | Risk: ${RISK_PER_TRADE} | Server: {broker_server} 🦅\n")

last_processed_candle_time = None
last_tracker_print = ""
active_tracker_id = None

# ==========================================
# 📊 3. DATA & CALCULATION FUNCTIONS
# ==========================================
def get_latest_data(symbol):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1500)
    if rates is None or len(rates) == 0: return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Calculate indicators
    df['EMA_285'] = ta.ema(df['close'], length=285)
    df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['RSI'] = ta.rsi(df['hlc3'], length=14)
    return df

def get_dynamic_lot(sl_distance):
    if sl_distance <= 0: return 0.01
    calculated_lot = RISK_PER_TRADE / (sl_distance * 100.0)
    final_lot = math.floor(calculated_lot * 100) / 100.0
    return max(0.01, min(final_lot, 50.0))

# ==========================================
# 🛡️ 4. EMERGENCY KILL SWITCH
# ==========================================
def emergency_close_all():
    print(f"\n🚨 KILL SWITCH TRIGGERED! Max Daily Loss Reached. Closing all positions...")
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
    quit() 

# ==========================================
# 🔫 5. EXECUTION ENGINE (SNIPER ENTRY)
# ==========================================
def execute_sniper_trade(direction, entry_price, sl_price, tp_price):
    sl_distance = abs(entry_price - sl_price)
    lot_size = get_dynamic_lot(sl_distance)
    
    print("\n" + "="*70)
    print(f"🔔 [{symbol}] SMC TRIGGERED | {direction}")
    print(f"🎯 Entry: {entry_price:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f} | Lot: {lot_size}")
    print("="*70)

    m_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL, 
        "symbol": symbol, 
        "volume": lot_size,
        "type": m_type, 
        "price": entry_price, 
        "sl": sl_price, 
        "tp": tp_price, 
        "magic": MAGIC_NUMBER, 
        "comment": f"SMC {direction}",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Order Failed! Code: {result.retcode}")
    else:
        print(f"🚀 Order Placed Successfully! Ticket: {result.order}")

# ==========================================
# 🧠 6. MAIN LIVE LOOP
# ==========================================
try:
    while True:
        current_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        time_hm = current_ist.hour * 100 + current_ist.minute
        
        global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
        if global_pos:
            floating_pnl = sum([p.profit + p.swap for p in global_pos])
            print(f"[{symbol}] Trade Active | Live PnL: ${floating_pnl:.2f}       ", end="\r")
            if floating_pnl <= MAX_DAILY_LOSS:
                emergency_close_all()
        else:
            print(f"[{symbol}] Scanning Market... ({current_ist.strftime('%H:%M:%S')} IST)       ", end="\r")

        if not global_pos:
            df = get_latest_data(symbol)
            
            if df is not None and len(df) > MAX_PATTERN_CANDLES:
                prev_candle = df.iloc[-2] 
                
                if last_processed_candle_time != prev_candle['time']:
                    current_setup_id = None
                    
                    if time_hm >= 1130:
                        close_p = df['close'].to_numpy()[:-1] 
                        high_p = df['high'].to_numpy()[:-1]
                        low_p = df['low'].to_numpy()[:-1]
                        open_p = df['open'].to_numpy()[:-1]
                        ema_p = df['EMA_285'].to_numpy()[:-1]
                        rsi_p = df['RSI'].to_numpy()[:-1]
                        
                        i = len(close_p) - 1
                        c_close, c_open, c_ema = close_p[i], open_p[i], ema_p[i]
                        
                        tick = mt5.symbol_info_tick(symbol)
                        if tick is None: continue

                        # 📈 BUY LOGIC (100% Backtesting logic: EMA & Green Candle Check)
                        if c_close > c_ema and c_close > c_open:
                            start_c = max(0, i - MAX_PATTERN_CANDLES)
                            c_idx = start_c + np.argmin(low_p[start_c : i])
                            c_low_val = low_p[c_idx]

                            if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                                start_b = max(0, c_idx - 15)
                                if start_b < c_idx:
                                    b_idx = start_b + np.argmax(high_p[start_b : c_idx])
                                    b_high_val = high_p[b_idx]

                                    start_a = max(0, b_idx - 15)
                                    if start_a < b_idx:
                                        a_idx = start_a + np.argmin(low_p[start_a : b_idx])
                                        a_low_val = low_p[a_idx]

                                        if c_low_val < a_low_val: 
                                            rsi_near_a = np.min(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                                            
                                            if rsi_near_a < 30.0: 
                                                current_setup_id = f"BUY_{a_idx}_{c_idx}"
                                                tracker_msg = f"🟢 BUY SETUP ACTIVE | Step 1: Point A ({a_low_val:.2f}) ✅ | Step 2: Sweep C ({c_low_val:.2f}) ✅ | Step 3: Pending BOS > {b_high_val:.2f} ⏳"
                                                
                                                if tracker_msg != last_tracker_print:
                                                    print(f"\n{tracker_msg}")
                                                    last_tracker_print = tracker_msg
                                                    
                                                if c_close > b_high_val: 
                                                    closes_since_c = close_p[c_idx+1 : i]
                                                    if not np.any(closes_since_c > b_high_val):
                                                        entry = tick.ask
                                                        sl_dist = max(0.50, entry - (c_low_val - SL_BUFFER))
                                                        sl = entry - sl_dist
                                                        tp = entry + (sl_dist * RR_MULTIPLIER)
                                                        execute_sniper_trade("BUY", entry, sl, tp)
                                                        current_setup_id = None
                                                        last_tracker_print = ""

                        # 📉 SELL LOGIC (100% Backtesting logic: EMA & Red Candle Check)
                        elif c_close < c_ema and c_close < c_open:
                            start_c = max(0, i - MAX_PATTERN_CANDLES)
                            c_idx = start_c + np.argmax(high_p[start_c : i])
                            c_high_val = high_p[c_idx]

                            if c_idx < (i - 1) and c_idx >= (i - MAX_PATTERN_CANDLES + 5):
                                start_b = max(0, c_idx - 15)
                                if start_b < c_idx:
                                    b_idx = start_b + np.argmin(low_p[start_b : c_idx])
                                    b_low_val = low_p[b_idx]

                                    start_a = max(0, b_idx - 15)
                                    if start_a < b_idx:
                                        a_idx = start_a + np.argmax(high_p[start_a : b_idx])
                                        a_high_val = high_p[a_idx]

                                        if c_high_val > a_high_val: 
                                            rsi_near_a = np.max(rsi_p[max(0, a_idx-2) : min(len(rsi_p), a_idx+3)])
                                            
                                            if rsi_near_a > 70.0: 
                                                current_setup_id = f"SELL_{a_idx}_{c_idx}"
                                                tracker_msg = f"🔴 SELL SETUP ACTIVE | Step 1: Point A ({a_high_val:.2f}) ✅ | Step 2: Sweep C ({c_high_val:.2f}) ✅ | Step 3: Pending BOS < {b_low_val:.2f} ⏳"
                                                
                                                if tracker_msg != last_tracker_print:
                                                    print(f"\n{tracker_msg}")
                                                    last_tracker_print = tracker_msg

                                                if c_close < b_low_val: 
                                                    closes_since_c = close_p[c_idx+1 : i]
                                                    if not np.any(closes_since_c < b_low_val):
                                                        entry = tick.bid
                                                        sl_dist = max(0.50, (c_high_val + SL_BUFFER) - entry)
                                                        sl = entry + sl_dist
                                                        tp = entry - (sl_dist * RR_MULTIPLIER)
                                                        execute_sniper_trade("SELL", entry, sl, tp)
                                                        current_setup_id = None
                                                        last_tracker_print = ""

                    # ⚠️ Setup Expiration/Interruption Professional Log
                    if active_tracker_id is not None and current_setup_id != active_tracker_id:
                        if current_setup_id is None:
                            print(f"\n⚠️ Setup Expired/Invalidated. Searching for new signal... 🦅")
                            last_tracker_print = ""
                    
                    active_tracker_id = current_setup_id
                    last_processed_candle_time = prev_candle['time']

        time.sleep(1) 
except KeyboardInterrupt:
    print("\n🛑 Bot Stopped by User.")
    mt5.shutdown()
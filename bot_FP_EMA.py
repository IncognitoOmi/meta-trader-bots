import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import math
from datetime import datetime, timedelta, timezone
import pytz

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 983347034 
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"
terminal_path = "c"

# Strategy Parameters
LOT_SIZE = 0.01
MAX_LOSS = -90.0          
MIN_TRAVEL_PRICE = 8.0
NEAR_THRESHOLD = 1.0     
CTC_BUFFER = 0.10        
MIN_ZONE_DIST = 3.0      # Next level must be at least $3 away from entry

if not mt5.initialize(path=terminal_path) or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ BOT LIVE | Pair: {symbol} | 1m EMA 200 Rejection Strategy 🦅\n")

# Trade State Variables
armed_near_miss = False
last_processed_candle = None

# ==========================================
# 🛡️ 2. HELPER FUNCTIONS
# ==========================================
def get_psych_level(price, is_tp, dir):
    if dir == "BUY":
        tp = math.ceil(price / 10.0) * 10.0
        avg = math.floor(price / 10.0) * 10.0
        
        if is_tp and (tp - price) < MIN_ZONE_DIST: tp += 10.0
        if not is_tp and (price - avg) < MIN_ZONE_DIST: avg -= 10.0
        return tp if is_tp else avg
        
    else: # SELL
        tp = math.floor(price / 10.0) * 10.0
        avg = math.ceil(price / 10.0) * 10.0
        
        if is_tp and (price - tp) < MIN_ZONE_DIST: tp -= 10.0
        if not is_tp and (avg - price) < MIN_ZONE_DIST: avg += 10.0
        return tp if is_tp else avg

def close_all_positions(reason=""):
    open_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
    if not open_pos: return
    
    print(f"\n🚨 CLOSING ALL POSITIONS | Reason: {reason}")
    for p in open_pos:
        tick = mt5.symbol_info_tick(p.symbol)
        if tick is None: continue
        type_dict = {mt5.POSITION_TYPE_BUY: mt5.ORDER_TYPE_SELL, mt5.POSITION_TYPE_SELL: mt5.ORDER_TYPE_BUY}
        price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol,
            "volume": p.volume, "type": type_dict[p.type], "price": price,
            "magic": MAGIC_NUMBER, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res.retcode != mt5.TRADE_RETCODE_DONE: print(f"Close Failed: {res.comment}")
    
    # Reset State
    global armed_near_miss
    armed_near_miss = False

def open_market_order(direction, comment="Entry"):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return
    
    m_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "BUY" else tick.bid
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": LOT_SIZE,
        "type": m_type, "price": price, 
        "magic": MAGIC_NUMBER, "comment": comment,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ {direction} Executed at {price:.2f} | {comment}")
    else:
        print(f"❌ Order Failed: {res.comment}")

def get_trend_and_distance(df):
    last_closed = df.iloc[-1] 
    trend = "UP" if last_closed['close'] > last_closed['EMA_200'] else "DOWN"
    extreme = last_closed['high'] if trend == "UP" else last_closed['low']

    # Walk backwards to find max distance since cross
    for i in range(len(df)-1, -1, -1):
        curr = df.iloc[i]
        if trend == "UP":
            if curr['close'] <= curr['EMA_200']: break
            extreme = max(extreme, curr['high'])
        else:
            if curr['close'] >= curr['EMA_200']: break
            extreme = min(extreme, curr['low'])

    dist_up = extreme - last_closed['EMA_200'] if trend == "UP" else 0
    dist_dn = last_closed['EMA_200'] - extreme if trend == "DOWN" else 0
    return dist_up, dist_dn

# ==========================================
# 🧠 3. MAIN EXECUTION ENGINE
# ==========================================
ist_tz = pytz.timezone("Asia/Kolkata")

try:
    while True:
        global_pos = mt5.positions_get(magic=MAGIC_NUMBER, symbol=symbol)
        num_pos = len(global_pos) if global_pos else 0
        tick = mt5.symbol_info_tick(symbol)
        
        if not tick: 
            time.sleep(1)
            continue
            
        now_ist = datetime.now(ist_tz).strftime("%H:%M:%S")

        # ----------------------------------
        # PHASE A: MANAGE ACTIVE TRADES
        # ----------------------------------
        if num_pos > 0:
            direction = "BUY" if global_pos[0].type == mt5.POSITION_TYPE_BUY else "SELL"
            current_price = tick.bid if direction == "BUY" else tick.ask
            floating_pnl = sum([p.profit + p.swap for p in global_pos])
            
            print(f"[{now_ist}] ACTIVE | {direction} | Layers: {num_pos} | PNL: ${floating_pnl:.2f} | C: {current_price:.2f}     ", end="\r")

            # 1. STOPLOSS Check
            if floating_pnl <= MAX_LOSS:
                close_all_positions(f"MAX LOSS HIT (${floating_pnl:.2f})")
                continue

            entry_price = global_pos[0].price_open
            tp_level = get_psych_level(entry_price, True, direction)
            avg_level = get_psych_level(entry_price, False, direction)

            # 2. HARD TP Hit Check
            if (direction == "BUY" and current_price >= tp_level) or (direction == "SELL" and current_price <= tp_level):
                close_all_positions(f"TAKE PROFIT @ {tp_level}")
                continue

            # 3. SCENARIO 3: Near Miss & CTC Logic (Fixed)
            if not armed_near_miss:
                dist_to_tp = abs(tp_level - entry_price)
                dist_to_avg = abs(avg_level - entry_price)
                
                # Check Near Miss towards Take Profit
                moved_towards_tp = (direction == "BUY" and current_price > entry_price) or (direction == "SELL" and current_price < entry_price)
                if moved_towards_tp and abs(current_price - tp_level) <= NEAR_THRESHOLD:
                    if dist_to_tp > NEAR_THRESHOLD: 
                        armed_near_miss = True
                        print(f"\n⚠️ [{now_ist}] Near TP Miss Armed! Bailout trap set.")
                
                # Check Near Miss towards Averaging Level
                moved_towards_avg = (direction == "BUY" and current_price < entry_price) or (direction == "SELL" and current_price > entry_price)
                if moved_towards_avg and abs(current_price - avg_level) <= NEAR_THRESHOLD:
                    if dist_to_avg > NEAR_THRESHOLD: 
                        armed_near_miss = True
                        print(f"\n⚠️ [{now_ist}] Near AVG Miss Armed! Bailout trap set.")

            # Bailout execution
            if armed_near_miss:
                if (direction == "BUY" and current_price <= (entry_price + CTC_BUFFER)) or \
                   (direction == "SELL" and current_price >= (entry_price - CTC_BUFFER)):
                    close_all_positions("CTC BAILOUT (Near Miss Reversal)")
                    continue

        # ----------------------------------
        # PHASE B: SCAN FOR ENTRIES/AVERAGING
        # ----------------------------------
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
        if rates is None: continue
        
        df = pd.DataFrame(rates)
        df['EMA_200'] = df['low'].ewm(span=200, adjust=False).mean()
        
        last_closed = df.iloc[-2]
        current_candle_time = int(last_closed['time'])
        
        if current_candle_time != last_processed_candle:
            ema = last_closed['EMA_200']
            c_close = last_closed['close']
            c_open = last_closed['open']
            
            # --- AVERAGING LOGIC (If 1 position open) ---
            if num_pos == 1:
                direction = "BUY" if global_pos[0].type == mt5.POSITION_TYPE_BUY else "SELL"
                avg_level = get_psych_level(global_pos[0].price_open, False, direction)
                
                if direction == "BUY" and last_closed['low'] <= avg_level and c_close > c_open:
                    open_market_order("BUY", comment="Layer 2 Average")
                    armed_near_miss = False 
                    last_processed_candle = current_candle_time
                    
                elif direction == "SELL" and last_closed['high'] >= avg_level and c_close < c_open:
                    open_market_order("SELL", comment="Layer 2 Average")
                    armed_near_miss = False 
                    last_processed_candle = current_candle_time
            
            # --- NEW ENTRY LOGIC (If Flat) ---
            elif num_pos == 0:
                # Anti-Breakout check: Calculate distance up to iloc[-3]
                df_prior = df.iloc[:-1] 
                dist_up, dist_dn = get_trend_and_distance(df_prior)
                
                print(f"[{now_ist}] SCANNING | C: {c_close:.2f} | EMA: {ema:.2f} | PriorUP: {dist_up:.2f} | PriorDN: {dist_dn:.2f}      ", end="\r")
                
                # BUY CONDITION
                if dist_up >= MIN_TRAVEL_PRICE and last_closed['low'] <= ema and c_close > ema:
                    if df.iloc[-3]['close'] > df.iloc[-3]['EMA_200']:
                        print(f"\n🚀 Valid BUY Rejection Found!")
                        open_market_order("BUY", comment="Initial Entry")
                        last_processed_candle = current_candle_time
                    
                # SELL CONDITION
                elif dist_dn >= MIN_TRAVEL_PRICE and last_closed['high'] >= ema and c_close < ema:
                    if df.iloc[-3]['close'] < df.iloc[-3]['EMA_200']:
                        print(f"\n🚀 Valid SELL Rejection Found!")
                        open_market_order("SELL", comment="Initial Entry")
                        last_processed_candle = current_candle_time

        time.sleep(1) 

except KeyboardInterrupt:
    print("\nBot Stopped by User.")
    mt5.shutdown()
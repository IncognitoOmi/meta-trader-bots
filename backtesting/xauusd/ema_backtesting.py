import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta, timezone
import math

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M1

account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"
terminal_path = "C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe"

STARTING_CAPITAL = 5000.0
MAX_LOSS = 100.0
LOT_SIZE = 0.05
CONTRACT_SIZE = 100.0 

MIN_TRAVEL_PRICE = 8.0  
NEAR_THRESHOLD = 1.0    
CTC_BUFFER = 0.10       

if not mt5.initialize(path=terminal_path) or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA & TIMEZONE FIX
# ==========================================
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=69) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# ---> BROUGHT BACK YOUR IST TIMEZONE CONVERSION <---
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df['EMA_200'] = ta.ema(df['low'], length=200)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# ==========================================
# 🧠 3. STRATEGY ENGINE
# ==========================================
running_capital = STARTING_CAPITAL
active_trade = False
direction = ""
orders = [] 
trade_entry_time = ""

highest_since_cross = 0.0
lowest_since_cross = float('inf')
near_tp_touched = False
near_avg_touched = False

def get_psych_level(price, is_tp, dir):
    if dir == "BUY":
        return math.ceil(price / 10.0) * 10.0 if is_tp else math.floor(price / 10.0) * 10.0
    else:
        return math.floor(price / 10.0) * 10.0 if is_tp else math.ceil(price / 10.0) * 10.0

def calc_floating_pnl(current_price, open_orders, dir):
    pnl = 0.0
    for price, lot in open_orders:
        if dir == "BUY":
            pnl += (current_price - price) * lot * CONTRACT_SIZE
        else:
            pnl += (price - current_price) * lot * CONTRACT_SIZE
    return pnl

print("\n" + "="*145)
print(f"{'IST ENTRY TIME':<22} | {'DIR':<4} | {'LAYERS':<6} | {'ENTRY ($)':<10} | {'EXIT ($)':<10} | {'OUTCOME (REASON)':<28} | {'PNL ($)':<10} | {'CAPITAL ($)'}")
print("="*145)

for i in range(1, len(df)):
    curr, prev = df.iloc[i], df.iloc[i-1]
    
    # Format the time nicely for the print output
    curr_time_str = curr['time'].strftime('%Y-%m-%d %H:%M:%S')
    ema = curr['EMA_200']
    
    if curr['close'] > ema:
        if prev['close'] <= prev['EMA_200']: lowest_since_cross = float('inf') 
        highest_since_cross = max(highest_since_cross, curr['high'])
    elif curr['close'] < ema:
        if prev['close'] >= prev['EMA_200']: highest_since_cross = 0.0 
        lowest_since_cross = min(lowest_since_cross, curr['low'])

    if active_trade:
        worst_price = curr['low'] if direction == "BUY" else curr['high']
        best_price = curr['high'] if direction == "BUY" else curr['low']
        floating_loss = calc_floating_pnl(worst_price, orders, direction)
        
        avg_entry = sum([p for p, l in orders]) / len(orders)
        
        # 1. HARD STOPLOSS HIT
        if floating_loss <= -MAX_LOSS:
            running_capital -= MAX_LOSS
            print(f"{trade_entry_time:<22} | {direction:<4} | {len(orders):<6} | {avg_entry:<10.2f} | {worst_price:<10.2f} | {'STOPLOSS (-$100)':<28} | -${MAX_LOSS:<9.2f} | ${running_capital:.2f}")
            active_trade = False
            continue
            
        tp_level = get_psych_level(orders[0][0], True, direction)
        avg_level = get_psych_level(orders[0][0], False, direction)
        
        if direction == "BUY":
            if best_price >= tp_level - NEAR_THRESHOLD: near_tp_touched = True
            if worst_price <= avg_level + NEAR_THRESHOLD: near_avg_touched = True
        else:
            if best_price <= tp_level + NEAR_THRESHOLD: near_tp_touched = True
            if worst_price >= avg_level - NEAR_THRESHOLD: near_avg_touched = True

        # 2. EARLY BAILOUT (Scenario 3 - Dynamic CTC)
        initial_entry = orders[0][0]
        price_returned = (direction == "BUY" and worst_price <= initial_entry) or (direction == "SELL" and worst_price >= initial_entry)
        
        if (near_tp_touched or near_avg_touched) and price_returned:
            exit_price = initial_entry + CTC_BUFFER if direction == "BUY" else initial_entry - CTC_BUFFER
            ctc_pnl = calc_floating_pnl(exit_price, orders, direction)
            running_capital += ctc_pnl
            print(f"{trade_entry_time:<22} | {direction:<4} | {len(orders):<6} | {avg_entry:<10.2f} | {exit_price:<10.2f} | {'CTC (Near Miss Reversal)':<28} | +${ctc_pnl:<9.2f} | ${running_capital:.2f}")
            active_trade = False
            continue

        # 3. TAKE PROFIT HIT
        tp_hit = (direction == "BUY" and best_price >= tp_level) or (direction == "SELL" and best_price <= tp_level)
        if tp_hit:
            pnl = calc_floating_pnl(tp_level, orders, direction)
            running_capital += pnl
            print(f"{trade_entry_time:<22} | {direction:<4} | {len(orders):<6} | {avg_entry:<10.2f} | {tp_level:<10.2f} | {f'TP @ {tp_level}':<28} | +${pnl:<9.2f} | ${running_capital:.2f}")
            active_trade = False
            continue

        # 4. AVERAGING (Scenario 2)
        if len(orders) == 1:
            if direction == "BUY" and worst_price <= avg_level:
                if curr['close'] > curr['open']: 
                    orders.append((avg_level, LOT_SIZE))
                    near_avg_touched = False 
            elif direction == "SELL" and worst_price >= avg_level:
                if curr['close'] < curr['open']: 
                    orders.append((avg_level, LOT_SIZE))
                    near_avg_touched = False

    if not active_trade:
        dist_pips_up = highest_since_cross - ema
        dist_pips_dn = ema - lowest_since_cross
        
        # BUY ENTRY
        if dist_pips_up >= MIN_TRAVEL_PRICE:
            if curr['low'] <= ema and curr['close'] > ema: 
                active_trade = True
                direction = "BUY"
                orders = [(curr['close'], LOT_SIZE)]
                trade_entry_time = curr_time_str
                near_tp_touched, near_avg_touched = False, False
                highest_since_cross = curr['high'] 
                
        # SELL ENTRY
        elif dist_pips_dn >= MIN_TRAVEL_PRICE:
             if curr['high'] >= ema and curr['close'] < ema: 
                active_trade = True
                direction = "SELL"
                orders = [(curr['close'], LOT_SIZE)]
                trade_entry_time = curr_time_str
                near_tp_touched, near_avg_touched = False, False
                lowest_since_cross = curr['low'] 

print("="*145)
print(f"🏁 Final Capital: ${running_capital:.2f}")
mt5.shutdown()
import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
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

STARTING_CAPITAL = 50000.0  
MAX_RISK = 500.0  
DAILY_DD_PCT = 0.04  
MAX_DD_PCT = 0.10    
MIN_SAFE_ATR = 1.5  
MAX_LAYERS = 2  
SL_ATR_MULT = MAX_LAYERS * 2  
RISK_MULT = sum(range(2, SL_ATR_MULT + 1, 2))  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA
# ==========================================
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=69) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df['EMA_200'] = ta.ema(df['close'], length=200)
df['RSI'] = ta.rsi(df['close'], length=9)
df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# ==========================================
# 🧠 3. STRATEGY ENGINE & DYNAMIC PNL
# ==========================================
tp_hits, sl_hits = 0, 0
total_pnl = 0.0 

# Phase & Prop Firm Variables
running_capital = STARTING_CAPITAL 
current_phase = 1
phase_1_target = STARTING_CAPITAL * 1.04  
phase_2_target = STARTING_CAPITAL * 1.08  
phase_3_payout_target = STARTING_CAPITAL * 1.08 # 8% Target for Withdrawals
max_loss_limit = STARTING_CAPITAL * (1 - MAX_DD_PCT)  
daily_start_balance = STARTING_CAPITAL

master_days_traded = 0
days_since_last_payout = 0
payouts_taken = 0
is_breached = False
current_day = None

# Daily limits
daily_losses = 0

active_trade = False
direction = ""
entry_price = tp = sl = current_lot = entry_rsi = entry_atr = 0
orders_open = 0 
entry_time = None
layers_prices = []

def get_fixed_atr(raw_atr):
    adj = raw_atr - 0.2
    return max(MIN_SAFE_ATR, round(adj, 2))

def get_dynamic_lot(fixed_atr):
    calculated_lot = MAX_RISK / (RISK_MULT * fixed_atr * 100.0)
    return max(0.01, min(math.floor(calculated_lot * 100) / 100.0, 10.0))

def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
    contract = 100.0
    pnl = (exit_p - e_p) if dir == "BUY" else (e_p - exit_p)
    for i in range(total_orders - 1):
        pnl += (exit_p - l_prices[i]) if dir == "BUY" else (l_prices[i] - exit_p)
    return pnl * lot * contract

print("\n" + "="*150)
print(f"{'TIME (IST)':<19} | {'ACTION / STATUS':<60} | {'RUNNING CAP'}")
print("="*150)

for i in range(1, len(df)):
    if is_breached:
        break

    curr, prev = df.iloc[i], df.iloc[i-1]
    curr_ist_time = curr['time']
    time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
    
    # Daily Tracking & Payout Logic
    trade_date = curr_ist_time.date()
    if current_day != trade_date:
        if current_day is not None:
            print(f"{str(current_day):<19} | 📅 End of Day Summary - Phase: {current_phase} | ${running_capital:.2f}")
            
            # Master Account Payout Check
            if current_phase == 3:
                master_days_traded += 1
                days_since_last_payout += 1
                
                # Check 10-day cycle AND 8% account profit rule
                if days_since_last_payout >= 10 and running_capital >= phase_3_payout_target:
                    payout_amount = 500.0
                    running_capital -= payout_amount
                    payouts_taken += 1
                    days_since_last_payout = 0
                    max_loss_limit = STARTING_CAPITAL 
                    print(f"{str(current_day):<19} | 💸 PAYOUT DAY! Withdrew ${payout_amount}. Account locked at $50k. | ${running_capital:.2f}")

        current_day = trade_date
        daily_start_balance = running_capital
        daily_losses = 0  

    if active_trade:
        exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
        
        if direction == "BUY":
            while orders_open < MAX_LAYERS and curr['low'] <= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
            if curr['low'] <= sl:
                sl_hits += 1
                daily_losses += 1
                pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                active_trade = False
                print(f"{exit_time_str:<19} | 🔴 SELL (SL Hit) PnL: -${abs(pnl):.2f} | ${running_capital:.2f}")
                
            elif curr['high'] >= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                active_trade = False
                print(f"{exit_time_str:<19} | 🟢 BUY (TP Hit) PnL: +${pnl:.2f} | ${running_capital:.2f}")
                
        elif direction == "SELL":
            while orders_open < MAX_LAYERS and curr['high'] >= layers_prices[orders_open - 1]:
                orders_open += 1
                if 2 <= orders_open <= 4:
                    tp = round(entry_price, 2)
                elif orders_open >= 5:
                    tp = round((entry_price + sum(layers_prices[:orders_open-1])) / orders_open, 2)
                    
            if curr['high'] >= sl:
                sl_hits += 1
                daily_losses += 1
                pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                active_trade = False
                print(f"{exit_time_str:<19} | 🔴 SELL (SL Hit) PnL: -${abs(pnl):.2f} | ${running_capital:.2f}")
                
            elif curr['low'] <= tp:
                tp_hits += 1
                pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
                total_pnl += pnl
                running_capital += pnl
                active_trade = False
                print(f"{exit_time_str:<19} | 🟢 SELL (TP Hit) PnL: +${pnl:.2f} | ${running_capital:.2f}")

        # Post-Trade Checks (Breach & Phase Pass)
        if not active_trade:
            daily_loss_limit = daily_start_balance * (1 - DAILY_DD_PCT)
            
            if running_capital <= max_loss_limit or running_capital <= daily_loss_limit:
                print(f"{exit_time_str:<19} | 🚨 ACCOUNT BREACHED! Hit Drawdown Limit. | ${running_capital:.2f}")
                is_breached = True
                
            if not is_breached:
                if current_phase == 1 and running_capital >= phase_1_target:
                    print(f"{exit_time_str:<19} | 🎉 PHASE 1 CLEARED! Resetting for Phase 2. | ${running_capital:.2f}")
                    current_phase = 2
                    running_capital = STARTING_CAPITAL
                    daily_start_balance = STARTING_CAPITAL
                    daily_losses = 0
                elif current_phase == 2 and running_capital >= phase_2_target:
                    print(f"{exit_time_str:<19} | 🎊 PHASE 2 CLEARED! Welcome to Master Account! | ${running_capital:.2f}")
                    current_phase = 3
                    running_capital = STARTING_CAPITAL
                    daily_start_balance = STARTING_CAPITAL
                    master_days_traded = 0
                    days_since_last_payout = 0
                    daily_losses = 0

    else:
        close, ema, rsi, raw_atr = prev['close'], prev['EMA_200'], prev['RSI'], prev['ATR']
        has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
        has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
        
        if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
            if daily_losses < 2:  
                if close > ema and rsi <= 31 and has_lower_wick:
                    direction = "BUY"
                    active_trade = True
                elif close < ema and rsi >= 69.8 and has_upper_wick:
                    direction = "SELL"
                    active_trade = True
                    
                if active_trade:
                    entry_atr = get_fixed_atr(raw_atr)
                    current_lot = get_dynamic_lot(entry_atr)
                    entry_price, entry_time = curr['open'], curr_ist_time
                    
                    if direction == "BUY":
                        sl = entry_price - (SL_ATR_MULT * entry_atr)
                        tp = entry_price + (2 * entry_atr)
                        layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                    else:
                        sl = entry_price + (SL_ATR_MULT * entry_atr)
                        tp = entry_price - (2 * entry_atr)
                        layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                        
                    orders_open = 1

print("="*150)
print(f"📊 SUMMARY | Phase Reached: {current_phase} | Total Payouts: ${payouts_taken * 500} | Breached: {is_breached}")
print("="*150)
mt5.shutdown()
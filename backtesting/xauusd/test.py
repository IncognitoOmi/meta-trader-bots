import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"

STARTING_CAPITAL = 5000.0  

# 🚨 MASTER (FUNDED) PROP FIRM RULES
MASTER_PAYOUT_TARGET = 5500
MASTER_PAYOUT_AMOUNT = 100
MASTER_MIN_PAYOUT_DAYS = 14
MASTER_DAILY_DD_LIMIT = 150         
MASTER_INITIAL_OVERALL_FLOOR = STARTING_CAPITAL * 0.95 
MASTER_TRAPDOOR_FLOOR = 5000.0      

# ⚙️ THE 7-PILLAR PDF RISK RULES
INITIAL_MAX_RISK = 20.0             
POST_PAYOUT_MAX_RISK = 20.0         
RR_RATIO = 5.0               # 👈 Target increased to 1:5 for consistency & stress-free math
BE_TRIGGER_RR = 2.5          # Move to BE at 1:2.5
SL_BUFFER = 0.50             

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH DATA & D1 BIAS (PILLAR 1)
# ==========================================
print("📥 Compiling 365 Days of Institutional Data...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365) 

# M15 Data (Structure)
rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_date - timedelta(days=5), end_date)
df_m15 = pd.DataFrame(rates_m15)
df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s').dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')
df_m15['date'] = df_m15['time'].dt.date

# Daily Bias (D1)
daily_data = df_m15.groupby('date').agg({'open': 'first', 'close': 'last', 'high': 'max', 'low': 'min'}).shift(1)
daily_data['D1_Bias'] = np.where(daily_data['close'] > daily_data['open'], 'BUY', 'SELL')
df_m15 = df_m15.merge(daily_data, on='date', suffixes=('', '_prev'))

# M1 Data (Execution)
rates_m1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
df_m1 = pd.DataFrame(rates_m1)
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s').dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')

df_m15.dropna(inplace=True); df_m1.dropna(inplace=True)

# ==========================================
# 🧠 3. EXTRACT STRICT POIs (PREMIUM/DISCOUNT & VALID PULLBACKS)
# ==========================================
valid_pois = []
leg_lookback = 40 # Roughly 10 hours for structural leg

for i in range(leg_lookback, len(df_m15) - 2):
    c0 = df_m15.iloc[i-1]; c1 = df_m15.iloc[i]
    c2 = df_m15.iloc[i+1]; c3 = df_m15.iloc[i+2]
    
    # Define Leg & Equilibrium (50%)
    leg_high = df_m15['high'].iloc[i-leg_lookback:i].max()
    leg_low = df_m15['low'].iloc[i-leg_lookback:i].min()
    eq_level = leg_low + ((leg_high - leg_low) * 0.5)
    
    # 🟢 BULLISH POI (Discount + Valid Pullback + FVG)
    if c1['D1_Bias'] == 'BUY' and c1['close'] < c1['open'] and c2['close'] > c2['open']:
        is_valid_pullback = c1['low'] < c0['low'] # No inside bars allowed
        in_discount = c1['low'] < eq_level        # Must be in bottom 50%
        has_fvg = c3['low'] > c1['high']
        
        if is_valid_pullback and in_discount and has_fvg:
            valid_pois.append({'type': 'BUY', 'top': c1['high'], 'bottom': c1['low'], 'time': c3['time'], 'active': True})
            
    # 🔴 BEARISH POI (Premium + Valid Pullback + FVG)
    elif c1['D1_Bias'] == 'SELL' and c1['close'] > c1['open'] and c2['close'] < c2['open']:
        is_valid_pullback = c1['high'] > c0['high'] # No inside bars allowed
        in_premium = c1['high'] > eq_level          # Must be in top 50%
        has_fvg = c3['high'] < c1['low']
        
        if is_valid_pullback and in_premium and has_fvg:
            valid_pois.append({'type': 'SELL', 'top': c1['high'], 'bottom': c1['low'], 'time': c3['time'], 'active': True})

print(f"✅ Found {len(valid_pois)} Ultra-Strict Institutional POIs.")

# ==========================================
# ⚙️ 4. SNIPER EXECUTION ENGINE (WAIT FOR CANDLE CLOSE)
# ==========================================
def get_lot(sl_dist, risk):
    if sl_dist <= 0: return 0.01
    return max(0.01, min(math.floor((risk / (sl_dist * 100.0)) * 100) / 100.0, 50.0))

running_cap = STARTING_CAPITAL
daily_floor = STARTING_CAPITAL - MASTER_DAILY_DD_LIMIT
overall_floor = MASTER_INITIAL_OVERALL_FLOOR
active_risk = INITIAL_MAX_RISK

trade_open = False
dir = entry = tp = sl = lot = 0
sl_to_be = False
current_day = None
payouts, win_count, loss_count, be_count = 0, 0, 0, 0
total_extracted = 0.0
trade_days = set()
blown = False

print("\n" + "="*120)
print(f"{'TIME (IST)':<19} | {'DIR':<4} | {'ENTRY':<8} | {'SL':<8} | {'TP':<8} | {'RES':<6} | {'PNL':<9} | {'BALANCE'}")
print("="*120)

for i in range(5, len(df_m1)):
    c_m1 = df_m1.iloc[i]        # Current Active Candle
    p_m1 = df_m1.iloc[i-1]      # Previously CLOSED Candle (Trigger)
    t_m1 = c_m1['time']
    d_m1 = t_m1.date()
    
    if d_m1 != current_day:
        current_day = d_m1
        daily_floor = running_cap - MASTER_DAILY_DD_LIMIT
    
    # 🟢 MANAGE OPEN TRADE
    if trade_open:
        closed = False; res = ""
        
        if dir == "BUY":
            if not sl_to_be and c_m1['high'] >= entry + (BE_TRIGGER_RR * (entry - sl)):
                sl = entry + 0.1; sl_to_be = True
            if c_m1['low'] <= sl:
                pnl = (sl - entry) * lot * 100.0; closed = True
                res = "BE" if sl_to_be else "LOSS"
                if sl_to_be: be_count += 1 
                else: loss_count += 1
            elif c_m1['high'] >= tp:
                pnl = (tp - entry) * lot * 100.0; closed = True; res = "WIN"; win_count += 1
                
        else:
            if not sl_to_be and c_m1['low'] <= entry - (BE_TRIGGER_RR * (sl - entry)):
                sl = entry - 0.1; sl_to_be = True
            if c_m1['high'] >= sl:
                pnl = (entry - sl) * lot * 100.0; closed = True
                res = "BE" if sl_to_be else "LOSS"
                if sl_to_be: be_count += 1 
                else: loss_count += 1
            elif c_m1['low'] <= tp:
                pnl = (entry - tp) * lot * 100.0; closed = True; res = "WIN"; win_count += 1

        if closed:
            trade_open = False
            running_cap += pnl
            trade_days.add(d_m1)
            print(f"{entry_time:<19} | {dir:<4} | {entry:<8.2f} | {sl:<8.2f} | {tp:<8.2f} | {res:<6} | {'+$' if pnl>=0 else '-$'}{abs(pnl):<8.2f} | ${running_cap:.2f}")
            
            if running_cap < daily_floor or running_cap < overall_floor:
                blown = True; break
                
            if running_cap >= MASTER_PAYOUT_TARGET and len(trade_days) >= MASTER_MIN_PAYOUT_DAYS:
                running_cap -= MASTER_PAYOUT_AMOUNT
                total_extracted += MASTER_PAYOUT_AMOUNT
                payouts += 1
                if payouts == 1:
                    overall_floor = MASTER_TRAPDOOR_FLOOR 
                    active_risk = POST_PAYOUT_MAX_RISK
                trade_days.clear()
                daily_floor = running_cap - MASTER_DAILY_DD_LIMIT
                print("-" * 120 + f"\n🎉 PAYOUT! Bal: ${running_cap:.2f} | Total Extracted: ${total_extracted:.2f}\n" + "-" * 120)

    # 🔍 SCAN FOR ENTRY (M1 CLOSED CANDLE ANALYSIS)
    if not trade_open and 13 <= t_m1.hour <= 22: # London/NY Session Only
        for ob in valid_pois:
            if not ob['active'] or ob['time'] > t_m1: continue
            
            # 📈 BULLISH IFC SWEEP
            if ob['type'] == 'BUY' and ob['bottom'] <= p_m1['low'] <= ob['top']:
                local_low = df_m1['low'].iloc[i-6:i-1].min()
                # strict rule: CLOSED candle must sweep low and close strong bullish
                if p_m1['low'] < local_low and p_m1['close'] > p_m1['open'] and p_m1['close'] > ob['bottom']:
                    trade_open = True; dir = "BUY"; entry = c_m1['open'] # Enter on new candle open
                    entry_time = t_m1.strftime('%Y-%m-%d %H:%M')
                    sl = p_m1['low'] - SL_BUFFER; dist = max(0.5, entry - sl)
                    tp = entry + (dist * RR_RATIO); lot = get_lot(dist, active_risk)
                    sl_to_be = False; ob['active'] = False; break

            # 📉 BEARISH IFC SWEEP
            elif ob['type'] == 'SELL' and ob['bottom'] <= p_m1['high'] <= ob['top']:
                local_high = df_m1['high'].iloc[i-6:i-1].max()
                # strict rule: CLOSED candle must sweep high and close strong bearish
                if p_m1['high'] > local_high and p_m1['close'] < p_m1['open'] and p_m1['close'] < ob['top']:
                    trade_open = True; dir = "SELL"; entry = c_m1['open'] # Enter on new candle open
                    entry_time = t_m1.strftime('%Y-%m-%d %H:%M')
                    sl = p_m1['high'] + SL_BUFFER; dist = max(0.5, sl - entry)
                    tp = entry - (dist * RR_RATIO); lot = get_lot(dist, active_risk)
                    sl_to_be = False; ob['active'] = False; break

print("="*120)
if blown: print("💀 ACCOUNT BLOWN")
else: print("🏆 SIMULATION COMPLETE")
print(f"🏦 Final Bal: ${running_cap:.2f} | Payouts: ${total_extracted:.2f} ({payouts})")
print(f"✅ Wins: {win_count} | ❌ Losses: {loss_count} | 🛡️ BEs: {be_count}")
win_rt = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0
print(f"🎯 Win Rate (Excl. BE): {win_rt:.2f}% (Targeting 1:5 RR)")
print("="*120)

mt5.shutdown()
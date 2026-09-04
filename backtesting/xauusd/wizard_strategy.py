import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import math
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M15  # 15-Min chart for Pullback Strategy
account_login = 12219217
account_password = "1Mz$YuVGJ"
broker_server = "FundingPips2-SIM"

STARTING_CAPITAL = 50000.0  
MAX_RISK = 200.0  # Strict Risk per trade
RR_RATIO = 2.0    # 1:2 Risk-Reward

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP_master/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()

# ==========================================
# 📊 2. FETCH HISTORICAL DATA (1 YEAR)
# ==========================================
print(f"📥 Fetching 1 Year of M15 data for {symbol}...")
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365) 

rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
if rates is None or len(rates) == 0:
    print("❌ No Data Fetched!")
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')
print(f"✅ Data Fetched! Total Candles: {len(df)}\n")

# ==========================================
# 🧠 3. PRE-CALCULATE INDICATORS
# ==========================================
df['EMA_8'] = ta.ema(df['close'], length=8)
df['EMA_30'] = ta.ema(df['close'], length=30)
df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14) 
df.dropna(inplace=True)

# 🚀 VECTORIZED ARRAYS FOR SPEED
opens = df['open'].values
highs = df['high'].values
lows = df['low'].values
closes = df['close'].values
ema8s = df['EMA_8'].values
ema30s = df['EMA_30'].values
atrs = df['ATR'].values

# ==========================================
# 🔫 4. FAST EXECUTION ENGINE
# ==========================================
wins, losses = 0, 0
total_pnl = 0.0
running_capital = STARTING_CAPITAL

active_trade = False
direction = ""
entry_price = tp = sl = risk_dist = current_lot = 0

length = len(opens)

print("⚡ Running 8/30 EMA Sniper Backtest...\n")

for i in range(1, length):
    curr_open = opens[i]
    curr_high = highs[i]
    curr_low = lows[i]
    
    if active_trade:
        if direction == "BUY":
            if curr_low <= sl:
                losses += 1
                total_pnl -= MAX_RISK
                running_capital -= MAX_RISK
                active_trade = False
            elif curr_high >= tp:
                wins += 1
                profit = MAX_RISK * RR_RATIO
                total_pnl += profit
                running_capital += profit
                active_trade = False
                
        elif direction == "SELL":
            if curr_high >= sl:
                losses += 1
                total_pnl -= MAX_RISK
                running_capital -= MAX_RISK
                active_trade = False
            elif curr_low <= tp:
                wins += 1
                profit = MAX_RISK * RR_RATIO
                total_pnl += profit
                running_capital += profit
                active_trade = False

    else:
        # Check Setup on Previous Closed Candle
        prev_open, prev_high, prev_low, prev_close = opens[i-1], highs[i-1], lows[i-1], closes[i-1]
        ema8, ema30, atr = ema8s[i-1], ema30s[i-1], atrs[i-1]
        
        # 📈 BUY SETUP
        if ema8 > ema30: # Trend is UP
            # Pullback condition: Low touched EMA 8, but Close is above EMA 30 + Bullish candle
            if prev_low < ema8 and prev_close > ema30 and prev_close > prev_open:
                active_trade = True
                direction = "BUY"
                entry_price = curr_open
                
                # SL slightly below the setup candle's low
                sl = prev_low - (0.5 * atr)
                risk_dist = entry_price - sl
                
                if risk_dist > 0:
                    tp = entry_price + (risk_dist * RR_RATIO)
                    current_lot = MAX_RISK / (risk_dist * 100)

        # 📉 SELL SETUP
        elif ema8 < ema30: # Trend is DOWN
            # Pullback condition: High touched EMA 8, but Close is below EMA 30 + Bearish candle
            if prev_high > ema8 and prev_close < ema30 and prev_close < prev_open:
                active_trade = True
                direction = "SELL"
                entry_price = curr_open
                
                # SL slightly above the setup candle's high
                sl = prev_high + (0.5 * atr)
                risk_dist = sl - entry_price
                
                if risk_dist > 0:
                    tp = entry_price - (risk_dist * RR_RATIO)
                    current_lot = MAX_RISK / (risk_dist * 100)

# ==========================================
# 🏆 5. FINAL REPORT
# ==========================================
total_trades = wins + losses
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

print("="*60)
print(f"🎯 8 & 30 EMA PULLBACK STRATEGY SUMMARY (1 YEAR)")
print("="*60)
print(f"📊 Total Trades : {total_trades}")
print(f"✅ Wins         : {wins}")
print(f"❌ Losses       : {losses}")
print(f"🎯 Win Rate     : {win_rate:.2f}%")
print("-" * 60)
print(f"💵 Risk/Reward  : 1:{RR_RATIO}")
print(f"💰 Net PnL      : ${total_pnl:.2f}")
print(f"🏦 Final Cap    : ${running_capital:.2f}")
print("="*60)

mt5.shutdown()
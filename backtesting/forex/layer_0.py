import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import math
from datetime import datetime, timedelta, timezone
import pytz

# ==========================================
# ⚙️ 1. SETTINGS & LOGIN
# ==========================================
timeframe = mt5.TIMEFRAME_M1
MAGIC_NUMBER = 720887034 
account_login = 12072180
account_password = "X[<P2r$d6"
broker_server = "FundingPips2-SIM"

STARTING_CAPITAL = 50000.0  
MAX_RISK = 1000.0  # Agar instant account ke liye test karna hai toh isko 45.0 kar dena

# 🚨 DYNAMIC GRID SETTINGS (1 Layer = 2 ATR SL, No Grid)
MAX_LAYERS = 1  
SL_ATR_MULT = MAX_LAYERS * 2  
RISK_MULT = sum(range(2, SL_ATR_MULT + 1, 2))  

if not mt5.initialize(path="C:/Program Files/MetaTrader 5 - FP2/terminal64.exe") or not mt5.login(login=account_login, password=account_password, server=broker_server):
    print("❌ MT5 Connection Fail!")
    quit()
print(f"✅ Bot ACTIVE | Multi-Pair Forex Backtesting 🦅\n")

# ==========================================
# 🧠 2. FOREX MULTI-PAIR CONFIGURATION
# ==========================================
PAIR_SETTINGS = {
    # === MAJORS ===
    # "EURUSD": {"min_atr": 0.0004, "atr_offset": 0.0001, "contract": 100000.0},
    "GBPUSD": {"min_atr": 0.0005, "atr_offset": 0.0001, "contract": 100000.0},
    # "USDJPY": {"min_atr": 0.030,  "atr_offset": 0.010,  "contract": 100000.0},
    "AUDUSD": {"min_atr": 0.0004, "atr_offset": 0.0001, "contract": 100000.0},
    # "USDCAD": {"min_atr": 0.0004, "atr_offset": 0.0001, "contract": 100000.0},
    # "USDCHF": {"min_atr": 0.0004, "atr_offset": 0.0001, "contract": 100000.0},
    # "NZDUSD": {"min_atr": 0.0004, "atr_offset": 0.0001, "contract": 100000.0},
    
    # === HIGH LIQUIDITY CROSSES ===
    "EURJPY": {"min_atr": 0.040,  "atr_offset": 0.010,  "contract": 100000.0},
    "GBPJPY": {"min_atr": 0.050,  "atr_offset": 0.010,  "contract": 100000.0},
    # "EURGBP": {"min_atr": 0.0003, "atr_offset": 0.0001, "contract": 100000.0},
    # "EURAUD": {"min_atr": 0.0005, "atr_offset": 0.0001, "contract": 100000.0},
    # "GBPAUD": {"min_atr": 0.0006, "atr_offset": 0.0001, "contract": 100000.0},
    "AUDJPY": {"min_atr": 0.030,  "atr_offset": 0.010,  "contract": 100000.0},
    # "CADJPY": {"min_atr": 0.030,  "atr_offset": 0.010,  "contract": 100000.0},
    # "CHFJPY": {"min_atr": 0.030,  "atr_offset": 0.010,  "contract": 100000.0},
}

end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=69) 

def run_backtest_for_symbol(symbol, settings):
    print("="*150)
    print(f"🚀 STARTING BACKTEST FOR: {symbol}")
    print("="*150)
    
    rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
    if rates is None or len(rates) == 0:
        print(f"❌ No Data Fetched for {symbol}! (Ensure symbol is visible in Market Watch)")
        return 0.0
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['time'] = df['time'].dt.tz_localize('Europe/Athens').dt.tz_convert('Asia/Kolkata')
    
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    tp_hits, sl_hits = 0, 0
    symbol_pnl = 0.0 
    
    active_trade = False
    direction = ""
    entry_price = tp = sl = current_lot = entry_rsi = entry_atr = 0
    orders_open = 0 
    entry_time = None
    layers_prices = []

    def get_fixed_atr(raw_atr):
        adj = raw_atr - settings["atr_offset"]
        round_digits = 3 if "JPY" in symbol else 5
        return max(settings["min_atr"], round(adj, round_digits))

    def get_dynamic_lot(fixed_atr):
        calculated_lot = MAX_RISK / (RISK_MULT * fixed_atr * settings["contract"])
        return max(0.01, min(math.floor(calculated_lot * 100) / 100.0, 10.0))

    def calc_exact_pnl(dir, exit_p, e_p, l_prices, total_orders, lot):
        pnl = (exit_p - e_p) if dir == "BUY" else (e_p - exit_p)
        for i in range(total_orders - 1):
            pnl += (exit_p - l_prices[i]) if dir == "BUY" else (l_prices[i] - exit_p)
        return pnl * lot * settings["contract"]

    print(f"{'ENTRY TIME (IST)':<19} | {'TYPE':<4} | {'RSI':<4} | {'ATR':<7} | {'ENTRY':<9} | {'EXIT TIME (IST)':<19} | {'EXIT':<9} | {'LOT':<4} | {'LAYERS':<6} | {'RESULT':<6} | {'TRADE PNL'}")
    print("-" * 150)

    for i in range(1, len(df)):
        curr, prev = df.iloc[i], df.iloc[i-1]
        curr_ist_time = curr['time']
        time_hm = curr_ist_time.hour * 100 + curr_ist_time.minute
        
        if active_trade:
            exit_time_str = curr_ist_time.strftime('%Y-%m-%d %H:%M')
            entry_time_str = entry_time.strftime('%Y-%m-%d %H:%M')
            
            if direction == "BUY":
                while orders_open < MAX_LAYERS and curr['low'] <= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = entry_price
                    elif orders_open >= 5:
                        tp = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                        
                if curr['low'] <= sl:
                    sl_hits += 1
                    pnl = calc_exact_pnl("BUY", sl, entry_price, layers_prices, orders_open, current_lot)
                    symbol_pnl += pnl
                    print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<7.5f} | {entry_price:<9.5f} | {exit_time_str:<19} | {sl:<9.5f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):.2f}")
                    active_trade = False
                    continue
                    
                elif curr['high'] >= tp:
                    tp_hits += 1
                    pnl = calc_exact_pnl("BUY", tp, entry_price, layers_prices, orders_open, current_lot)
                    symbol_pnl += pnl
                    print(f"{entry_time_str:<19} | BUY  | {entry_rsi:<4.1f} | {entry_atr:<7.5f} | {entry_price:<9.5f} | {exit_time_str:<19} | {tp:<9.5f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:.2f}")
                    active_trade = False
                    
            elif direction == "SELL":
                while orders_open < MAX_LAYERS and curr['high'] >= layers_prices[orders_open - 1]:
                    orders_open += 1
                    if 2 <= orders_open <= 4:
                        tp = entry_price
                    elif orders_open >= 5:
                        tp = (entry_price + sum(layers_prices[:orders_open-1])) / orders_open
                        
                if curr['high'] >= sl:
                    sl_hits += 1
                    pnl = calc_exact_pnl("SELL", sl, entry_price, layers_prices, orders_open, current_lot)
                    symbol_pnl += pnl
                    print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<7.5f} | {entry_price:<9.5f} | {exit_time_str:<19} | {sl:<9.5f} | {current_lot:<4.2f} | {orders_open - 1:<6} | LOSS   | -${abs(pnl):.2f}")
                    active_trade = False
                    continue
                    
                elif curr['low'] <= tp:
                    tp_hits += 1
                    pnl = calc_exact_pnl("SELL", tp, entry_price, layers_prices, orders_open, current_lot)
                    symbol_pnl += pnl
                    print(f"{entry_time_str:<19} | SELL | {entry_rsi:<4.1f} | {entry_atr:<7.5f} | {entry_price:<9.5f} | {exit_time_str:<19} | {tp:<9.5f} | {current_lot:<4.2f} | {orders_open - 1:<6} | WIN    | +${pnl:.2f}")
                    active_trade = False

        else:
            close, ema, rsi, raw_atr = prev['close'], prev['EMA_200'], prev['RSI'], prev['ATR']
            has_lower_wick = prev['low'] < prev['open'] and prev['low'] < prev['close']
            has_upper_wick = prev['high'] > prev['open'] and prev['high'] > prev['close']
            
            if time_hm >= 1130 and not (1700 <= time_hm <= 1800):
                if close > ema and rsi <= 31 and has_lower_wick:
                    direction = "BUY"
                    active_trade = True
                elif close < ema and rsi >= 69.8 and has_upper_wick:
                    direction = "SELL"
                    active_trade = True
                    
                if active_trade:
                    entry_atr = get_fixed_atr(raw_atr)
                    current_lot = get_dynamic_lot(entry_atr)
                    entry_price, entry_time, entry_rsi = curr['open'], curr_ist_time, round(rsi, 1)
                    
                    if direction == "BUY":
                        sl = entry_price - (SL_ATR_MULT * entry_atr)
                        tp = entry_price + (2 * entry_atr)
                        layers_prices = [entry_price - (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                    else:
                        sl = entry_price + (SL_ATR_MULT * entry_atr)
                        tp = entry_price - (2 * entry_atr)
                        layers_prices = [entry_price + (i * 2 * entry_atr) for i in range(1, MAX_LAYERS)]
                        
                    orders_open = 1
                    
    print(f"\n📊 {symbol} SUMMARY: Wins: {tp_hits} | Losses: {sl_hits} | Net PnL: ${symbol_pnl:.2f}\n")
    return symbol_pnl

# ==========================================
# 🚀 EXECUTE MULTI-PAIR BACKTEST
# ==========================================
grand_total_pnl = 0.0
pair_results = {}

for sym, settings in PAIR_SETTINGS.items():
    symbol_pnl = run_backtest_for_symbol(sym, settings)
    grand_total_pnl += symbol_pnl
    pair_results[sym] = symbol_pnl

final_capital = STARTING_CAPITAL + grand_total_pnl

print("="*150)
print(f"🏆 FINAL PORTFOLIO SUMMARY | Starting Capital: ${STARTING_CAPITAL:.2f}")
print("="*150)

# Sort pairs by profit to see the winners and losers easily
sorted_pairs = sorted(pair_results.items(), key=lambda x: x[1], reverse=True)
for pair, pnl in sorted_pairs:
    status = "🟢" if pnl >= 0 else "🔴"
    print(f"{status} {pair:<10} : ${pnl:.2f}")

print("-" * 150)
print(f"💰 Total Net PnL Across All Pairs: ${grand_total_pnl:.2f}")
print(f"🏦 Final Portfolio Capital: ${final_capital:.2f}")

mt5.shutdown()
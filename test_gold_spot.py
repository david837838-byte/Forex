import yfinance as yf

for sym in ['XAU-USD', 'XAUUSD=X', 'GC=F', 'GOLD']:
    try:
        t = yf.Ticker(sym)
        price = t.fast_info.last_price or t.fast_info.previous_close
        print(f"SYMBOL: {sym} -> PRICE: {price}")
    except Exception as e:
        print(f"SYMBOL: {sym} -> ERROR: {e}")

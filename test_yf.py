import yfinance as yf

symbols = ['GC=F', 'XAUUSD=X', 'CL=F', 'EURUSD=X', 'BTC-USD']
print("--- TESTING YFINANCE TICKERS ---")
for s in symbols:
    try:
        t = yf.Ticker(s)
        p = t.fast_info.last_price or t.fast_info.previous_close
        print(f"{s}: {p}")
    except Exception as e:
        print(f"{s} ERROR: {e}")

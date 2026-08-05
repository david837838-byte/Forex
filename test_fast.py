import yfinance as yf
import time

t0 = time.time()
df = yf.download(['GC=F', 'SI=F', 'CL=F', 'EURUSD=X', 'BTC-USD', 'JPY=X', '^DJI', 'NVDA', 'TSLA'], period='1d', interval='1m', progress=False)
t1 = time.time()

print(f"Batch fetch time: {t1 - t0:.2f} seconds")
print("Latest Close values:")
if not df.empty and 'Close' in df:
    latest = df['Close'].iloc[-1]
    print(latest)

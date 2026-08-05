import urllib.request
import json

def test_perfect_tradingview_symbols():
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {
            "tickers": [
                "TVC:GOLD", "OANDA:XAUUSD",
                "TVC:SILVER", "OANDA:XAGUSD",
                "OANDA:WTICOUSD", "NYMEX:CL1!",
                "NYMEX:NG1!",
                "OANDA:EURUSD", "OANDA:GBPUSD", "OANDA:USDJPY",
                "OANDA:USDCHF", "OANDA:USDCAD", "OANDA:AUDUSD", "OANDA:NZDUSD",
                "CBOT:YM1!", "INDEX:DOWI", "FOREXCOM:US30",
                "CME:NQ1!", "INDEX:IUXX", "FOREXCOM:NSXUSD",
                "NASDAQ:NVDA", "NASDAQ:TSLA", "NASDAQ:AAPL",
                "BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"
            ]
        },
        "columns": ["close", "change"]
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print("--- PERFECT TRADINGVIEW SYMBOLS RESULTS ---")
            for item in data.get('data', []):
                ticker = item.get('s')
                vals = item.get('d', [])
                print(f"{ticker}: close={vals[0]} (change={vals[1]:.2f}%)")
    except Exception as e:
        print(f"Error: {e}")

test_perfect_tradingview_symbols()

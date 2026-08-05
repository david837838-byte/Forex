import urllib.request
import json

def test_tv_symbols_scan():
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {
            "tickers": [
                "TVC:GOLD", "OANDA:XAUUSD",
                "TVC:SILVER", "OANDA:XAGUSD",
                "TVC:USOIL", "OANDA:WTICOUSD",
                "OANDA:GBPUSD", "FX_IDC:GBPUSD",
                "FOREXCOM:DJI", "INDEX:DOWI", "TVC:US30", "CBOT:YM1!",
                "NASDAQ:NVDA", "NVDA",
                "NASDAQ:TSLA", "TSLA",
                "NASDAQ:AAPL", "AAPL"
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
            print("--- TRADINGVIEW TICKER RESULTS ---")
            for item in data.get('data', []):
                ticker = item.get('s')
                vals = item.get('d', [])
                print(f"{ticker}: close={vals[0] if len(vals)>0 else 'N/A'}")
    except Exception as e:
        print(f"Error: {e}")

test_tv_symbols_scan()

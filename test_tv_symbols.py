import urllib.request
import json

def test_all_tv_gold_symbols():
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {
            "tickers": [
                "TVC:GOLD", "OANDA:XAUUSD", "FX_IDC:XAUUSD",
                "FOREXCOM:XAUUSD", "CAPITALCOM:GOLD", "SAXO:XAUUSD"
            ]
        },
        "columns": ["close", "change", "change_abs"]
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print("--- TRADINGVIEW ALL GOLD TICKERS ---")
            for item in data.get('data', []):
                ticker = item.get('s')
                vals = item.get('d', [])
                close_price = vals[0] if len(vals) > 0 else None
                pct_change = vals[1] if len(vals) > 1 else None
                print(f"TRADINGVIEW {ticker}: ${close_price} ({pct_change:.2f}%)")
    except Exception as e:
        print(f"Error: {e}")

test_all_tv_gold_symbols()

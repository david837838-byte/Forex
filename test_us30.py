import urllib.request
import json

def test_us30_scan():
    url = "https://scanner.tradingview.com/cfd/scan"
    payload = {
        "symbols": {
            "tickers": ["FOREXCOM:DJI", "INDEX:DOWI", "TVC:US30", "CBOT:YM1!", "OANDA:US30USD"]
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
            print("--- US30 CFD SCANNER RESULTS ---")
            for item in data.get('data', []):
                ticker = item.get('s')
                vals = item.get('d', [])
                print(f"{ticker}: close={vals[0]} (change={vals[1]:.2f}%)")
    except Exception as e:
        print(f"Error: {e}")

test_us30_scan()

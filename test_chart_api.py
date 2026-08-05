import urllib.request
import json

def test_yahoo_chart_api(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            meta = data['chart']['result'][0]['meta']
            price = meta['regularMarketPrice']
            prev = meta.get('chartPreviousClose', price)
            print(f"SYMBOL {symbol} -> PRICE: {price}, PREV: {prev}")
            return price
    except Exception as e:
        print(f"SYMBOL {symbol} -> ERROR: {e}")
        return None

for s in ['GC=F', 'XAUUSD=X', 'SI=F', 'CL=F', '^DJI', 'NVDA', 'TSLA']:
    test_yahoo_chart_api(s)

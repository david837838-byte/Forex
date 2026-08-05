import urllib.request
import json

def test_spot_sources():
    # Source 1: GoldPrice.org Official Live Spot Stream
    try:
        url = "https://data-asg.goldprice.org/dbwr/gold_price_usd"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            price = data.get('items', [{}])[0].get('xauPrice')
            print(f"GOLDPRICE.ORG LIVE SPOT GOLD: ${price}")
    except Exception as e:
        print(f"GoldPrice error: {e}")

    # Source 2: Metals API / Frankfurter / Exchange Rate
    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print("FRANKFURTER RATES:", data.get('rates'))
    except Exception as e:
        print(f"Frankfurter error: {e}")

test_spot_sources()

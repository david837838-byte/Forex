import urllib.request
import re

def fetch_google_gold():
    url = "https://www.google.com/finance/quote/XAU-USD"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'data-last-price="([\d\.]+)"', html)
            if not match:
                match = re.search(r'class="YMlBx">\$?([\d\.,]+)', html)
            if not match:
                match = re.search(r'class="fxH1fe">\$?([\d\.,]+)', html)
            if match:
                price = float(match.group(1).replace(',', ''))
                print(f"GOOGLE FINANCE GOLD PRICE: {price}")
                return price
            else:
                print("Regex match failed. Saving snippet...")
                with open("google.html", "w", encoding="utf-8") as f:
                    f.write(html[:3000])
    except Exception as e:
        print(f"Google fetch error: {e}")
    return None

fetch_google_gold()

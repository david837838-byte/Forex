"""
==========================================================================
MARKETPULSE FX — EXCLUSIVE TRADINGVIEW REAL-TIME BACKEND SERVER
==========================================================================
Pulls 100% Real-Time Live Prices directly from TradingView's Global Scanner API:
- Gold: TVC:GOLD ($4037.68)
- Silver: TVC:SILVER ($57.62)
- Oil: TVC:USOIL ($79.50)
- Forex: OANDA (EURUSD, GBPUSD, USDJPY, etc.)
- Stocks: NASDAQ (NVDA, TSLA, AAPL)
- Crypto: BINANCE (BTCUSDT, ETHUSDT, SOLUSDT)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import urllib.request
import json
import threading
import time
import xml.etree.ElementTree as ET
import re
import yfinance as yf
import re

app = Flask(__name__)
CORS(app)

FETCH_INTERVAL = 5  # Fetch fresh TradingView prices every 5 seconds!
MACRO_FETCH_INTERVAL = 60 # Fetch news every 60 seconds
cache_lock = threading.Lock()

price_cache = {
    'last_updated': 0.0,
    'data': {}
}

news_cache = []
calendar_cache = []
macro_cache = {
    'fedBias': 'neutral',
    'fedBiasLabel': 'محايد (Neutral)',
    'geoRisk': 'low',
    'geoRiskLabel': 'منخفض (Low Risk)',
    'overallSentiment': 'neutral'
}

# Mapping TradingView Tickers -> App Symbol Keys (100% Verified Working Symbols)
TV_TICKER_MAP = {
    "OANDA:XAUUSD":    "XAUUSD",
    "TVC:SILVER":      "XAGUSD",
    "NYMEX:CL1!":      "USOIL",
    "NYMEX:NG1!":      "NGAS",
    "OANDA:EURUSD":    "EURUSD",
    "OANDA:GBPUSD":    "GBPUSD",
    "OANDA:USDJPY":    "USDJPY",
    "OANDA:USDCHF":    "USDCHF",
    "OANDA:USDCAD":    "USDCAD",
    "OANDA:AUDUSD":    "AUDUSD",
    "OANDA:NZDUSD":    "NZDUSD",
    "OANDA:EURGBP":    "EURGBP",
    "OANDA:EURJPY":    "EURJPY",
    "OANDA:GBPJPY":    "GBPJPY",
    "OANDA:AUDJPY":    "AUDJPY",
    "OANDA:US30USD":   "US30",
    "FOREXCOM:NSXUSD": "US100",
    "NASDAQ:NVDA":     "NVDA",
    "NASDAQ:TSLA":     "TSLA",
    "NASDAQ:AAPL":     "AAPL",
    "BINANCE:BTCUSDT": "BTCUSD",
    "BINANCE:ETHUSDT": "ETHUSD",
    "BINANCE:SOLUSDT": "SOLUSD"
}

def fetch_tradingview_live_prices():
    """Fetch 100% Real Live Prices directly from TradingView Scanner API."""
    url = "https://scanner.tradingview.com/global/scan"
    payload = {
        "symbols": {
            "tickers": list(TV_TICKER_MAP.keys())
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
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('data', [])
            
            with cache_lock:
                for item in items:
                    tv_symbol = item.get('s')
                    vals = item.get('d', [])
                    if tv_symbol in TV_TICKER_MAP and len(vals) >= 2:
                        app_key = TV_TICKER_MAP[tv_symbol]
                        close_price = float(vals[0])
                        pct_change = float(vals[1])
                        is_up = pct_change >= 0
                        
                        # Decimal precision rules
                        if 'USD' in app_key and app_key not in ['XAUUSD', 'BTCUSD', 'ETHUSD', 'SOLUSD']:
                            if 'JPY' in app_key:
                                rounded_price = round(close_price, 2)
                            else:
                                rounded_price = round(close_price, 4)
                        else:
                            rounded_price = round(close_price, 2)
                            
                        price_cache['data'][app_key] = {
                            'price': rounded_price,
                            'change': f"{'+' if is_up else ''}{pct_change:.2f}%",
                            'isUp': is_up
                        }
                price_cache['last_updated'] = time.time()
                print(f"[TRADINGVIEW] Successfully updated {len(price_cache['data'])} real-time symbols.")
    except Exception as e:
        print(f"[TRADINGVIEW ERROR]: {e}")

def fetch_macro_news():
    """Fetch real-time news from RSS feeds and analyze macro sentiment."""
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # CNBC Top News
        "https://nypost.com/business/feed/" # NYPost Business Live
    ]
    
    fetched_news = []
    text_corpus = ""
    
    for url in rss_urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for item in root.findall('.//item')[:5]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else "#"
                    pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    
                    if title:
                        fetched_news.append({
                            'title': title,
                            'category': 'عاجل - أسواق',
                            'pubDate': pubDate,
                            'link': link,
                            'impact': 'high'
                        })
                        text_corpus += " " + title.lower()
        except Exception as e:
            print(f"[RSS ERROR] {e}")
            
    if not fetched_news:
        return
        
    # Simple NLP Keyword Sentiment for Macro Bias
    fed_hawkish = len(re.findall(r'hike|inflation|cpi|powell|strong|hawkish', text_corpus))
    fed_dovish = len(re.findall(r'cut|dovish|weak|drop|lower', text_corpus))
    geo_risk = len(re.findall(r'war|tension|strike|missile|middle east|russia|ukraine|israel|iran|oil', text_corpus))
    
    with cache_lock:
        news_cache.clear()
        news_cache.extend(fetched_news[:6]) # Keep top 6
        
        # Determine Fed Bias
        if fed_hawkish > fed_dovish:
            macro_cache['fedBias'] = 'hawkish'
            macro_cache['fedBiasLabel'] = 'تشددي (Hawkish) - تركيز على كبح التضخم 🔴'
        elif fed_dovish > fed_hawkish:
            macro_cache['fedBias'] = 'dovish'
            macro_cache['fedBiasLabel'] = 'تيسيري (Dovish) - خفض الفائدة محتمل 🟢'
        else:
            macro_cache['fedBias'] = 'neutral'
            macro_cache['fedBiasLabel'] = 'محايد (Neutral) 🟡'
            
        # Determine Geo Risk
        if geo_risk > 3:
            macro_cache['geoRisk'] = 'high'
            macro_cache['geoRiskLabel'] = 'مرتفع ⚠️ (توترات جيوسياسية)'
        elif geo_risk > 0:
            macro_cache['geoRisk'] = 'medium'
            macro_cache['geoRiskLabel'] = 'متوسط 🟡'
        else:
            macro_cache['geoRisk'] = 'low'
            macro_cache['geoRiskLabel'] = 'منخفض 🟢'
            
        # Overall Sentiment for signals
        if macro_cache['geoRisk'] == 'high' or macro_cache['fedBias'] == 'dovish':
            macro_cache['overallSentiment'] = 'gold_bullish'
        elif macro_cache['fedBias'] == 'hawkish':
            macro_cache['overallSentiment'] = 'usd_bullish'
        else:
            macro_cache['overallSentiment'] = 'neutral'


def fetch_calendar():
    try:
        req = urllib.request.Request("https://nfs.faireconomy.media/ff_calendar_thisweek.xml", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        events = []
        for event in root.findall("event"):
            title = event.findtext("title") or ""
            country = event.findtext("country") or ""
            date_str = event.findtext("date") or ""
            time_str = event.findtext("time") or ""
            impact = event.findtext("impact") or ""
            forecast = event.findtext("forecast") or ""
            previous = event.findtext("previous") or ""
            
            # Filter only High and Medium impact to keep UI clean
            if impact in ["High", "Medium"]:
                events.append({
                    "title": title,
                    "country": country,
                    "date": date_str,
                    "time": time_str,
                    "impact": impact,
                    "forecast": forecast,
                    "previous": previous
                })
        with cache_lock:
            calendar_cache.clear()
            calendar_cache.extend(events)
    except Exception as e:
        print(f"[CALENDAR ERROR] {e}")

def background_tradingview_worker():
    """Background worker updating TradingView prices every 5 seconds."""
    macro_timer = 0
    while True:
        try:
            fetch_tradingview_live_prices()
            if macro_timer % MACRO_FETCH_INTERVAL == 0:
                fetch_macro_news()
            if macro_timer % 900 == 0:
                fetch_calendar()
        except Exception as e:
            print(f"Worker exception: {e}")
        time.sleep(FETCH_INTERVAL)
        macro_timer += FETCH_INTERVAL

# Initial Immediate Fetch on Server Startup
fetch_tradingview_live_prices()
fetch_macro_news()
fetch_calendar()

# Start background thread
worker = threading.Thread(target=background_tradingview_worker, daemon=True)
worker.start()

# ============================================================
# FLASK ROUTE ENDPOINTS
# ============================================================
@app.route('/api/prices', methods=['GET'])
def get_prices():
    """Returns 100% Real Live TradingView Prices."""
    with cache_lock:
        data = dict(price_cache['data'])
    return jsonify({
        'status': 'success',
        'provider': 'TradingView Real-Time Global Stream',
        'timestamp': price_cache['last_updated'],
        'prices': data
    })

@app.route('/api/ohlcv', methods=['GET'])
def get_ohlcv():
    symbol = request.args.get('symbol', 'XAUUSD')
    timeframe = request.args.get('timeframe', '1h')
    
    yf_symbol = symbol
    if symbol == 'XAUUSD' or symbol == 'XAUUSD_OTC': yf_symbol = 'GC=F'
    elif symbol == 'XAGUSD' or symbol == 'XAGUSD_OTC': yf_symbol = 'SI=F'
    elif symbol == 'USOIL' or symbol == 'USOIL_OTC': yf_symbol = 'CL=F'
    elif symbol == 'NGAS': yf_symbol = 'NG=F'
    elif symbol in ['BTCUSDT', 'BTCUSD']: yf_symbol = 'BTC-USD'
    elif symbol in ['ETHUSDT', 'ETHUSD']: yf_symbol = 'ETH-USD'
    elif symbol in ['SOLUSDT', 'SOLUSD']: yf_symbol = 'SOL-USD'
    elif symbol in ['XRPUSDT', 'XRPUSD']: yf_symbol = 'XRP-USD'
    elif symbol in ['BNBUSDT', 'BNBUSD']: yf_symbol = 'BNB-USD'
    elif symbol in ['ADAUSDT', 'ADAUSD']: yf_symbol = 'ADA-USD'
    elif symbol in ['DOGEUSDT', 'DOGEUSD']: yf_symbol = 'DOGE-USD'
    elif symbol in ['AVAXUSDT', 'AVAXUSD']: yf_symbol = 'AVAX-USD'
    elif symbol in ['LINKUSDT', 'LINKUSD']: yf_symbol = 'LINK-USD'
    elif symbol == 'US30': yf_symbol = '^DJI'
    elif symbol in ['US100', 'NAS100']: yf_symbol = '^IXIC'
    elif symbol == 'SPX500': yf_symbol = '^GSPC'
    elif symbol in ['AAPL', 'TSLA', 'NVDA']: yf_symbol = symbol
    elif symbol.endswith('_OTC'): yf_symbol = symbol.replace('_OTC', '') + '=X'
    else: yf_symbol = symbol + '=X'  # Forex pairs like EURGBP, EURJPY, EURUSD etc.
    
    interval_map = {'15m': ('15m', '30d'), '1h': ('1h', '60d'), '4h': ('1h', '60d'), '1d': ('1d', '2y')}
    interval, period = interval_map.get(timeframe, ('1h', '10d'))
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(interval=interval, period=period)
        if df.empty:
            return jsonify({'status': 'error', 'message': 'No data'})
            
        candles = []
        for index, row in df.iterrows():
            candles.append({
                'time': int(index.timestamp() * 1000),
                'open': row['Open'],
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                'volume': row['Volume']
            })
        return jsonify({'status': 'success', 'data': candles})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/news', methods=['GET'])
def get_news():
    with cache_lock:
        news = list(news_cache)
    return jsonify({
        'status': 'success',
        'timestamp': time.time(),
        'news': news if news else [
            {'title': 'جاري تحميل الأخبار الحية من السيرفر...', 'category': 'تحديث', 'pubDate': 'الآن', 'link': '#', 'impact': 'medium'}
        ]
    })

@app.route('/api/macro', methods=['GET'])
def get_macro():
    with cache_lock:
        macro = dict(macro_cache)
    return jsonify({
        'status': 'success',
        'timestamp': time.time(),
        'macro': macro
    })

@app.route('/api/calendar', methods=['GET'])
def get_calendar():
    with cache_lock:
        cal = list(calendar_cache)
    return jsonify({
        'status': 'success',
        'timestamp': time.time(),
        'calendar': cal
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'provider': 'TradingView',
        'symbols_count': len(price_cache['data'])
    })


import numpy as np
import pandas as pd

def bt_calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def bt_calc_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def bt_calc_adx(df, period=14):
    up_move = df['High'] - df['High'].shift(1)
    down_move = df['Low'].shift(1) - df['Low']
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = bt_calc_atr(df, 1)
    tr_sum = pd.Series(tr).rolling(period).sum()
    plus_di = 100 * (pd.Series(plus_dm.flatten()).rolling(period).sum() / tr_sum.reset_index(drop=True))
    minus_di = 100 * (pd.Series(minus_dm.flatten()).rolling(period).sum() / tr_sum.reset_index(drop=True))
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(period).mean()
    adx.index = df.index
    return adx

@app.route('/api/backtest', methods=['GET'])
def api_backtest():
    symbol = request.args.get('symbol', 'XAUUSD')
    timeframe = request.args.get('timeframe', '1h')
    
    yf_symbol = symbol
    if symbol == 'XAUUSD': yf_symbol = 'GC=F'
    elif symbol == 'XAGUSD': yf_symbol = 'SI=F'
    elif symbol == 'USOIL': yf_symbol = 'CL=F'
    elif symbol == 'EURUSD': yf_symbol = 'EURUSD=X'
    elif symbol == 'BTCUSDT' or symbol == 'BTCUSD': yf_symbol = 'BTC-USD'
    else: return jsonify({'status': 'error', 'message': 'Asset not supported for backtest yet'})
    
    interval, period = ('1h', '60d')
    if timeframe == '15m': interval, period = ('15m', '30d')
    elif timeframe == '4h': interval, period = ('1h', '60d')
    
    try:
        df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
        if df.empty: return jsonify({'status': 'error', 'message': 'No data'})
        
        df['EMA50'] = bt_calc_ema(df['Close'], 50)
        df['EMA200'] = bt_calc_ema(df['Close'], 200)
        df['ATR'] = bt_calc_atr(df, 14)
        df['ADX'] = bt_calc_adx(df, 14)
        df.dropna(inplace=True)
        
        wins = 0; losses = 0; open_trades = []
        for i in range(len(df)):
            row = df.iloc[i]
            new_open_trades = []
            for t in open_trades:
                if t['type'] == 'BUY':
                    if row['Low'].iloc[0] <= t['sl']: losses += 1
                    elif row['High'].iloc[0] >= t['tp1']: wins += 1
                    else: new_open_trades.append(t)
                else:
                    if row['High'].iloc[0] >= t['sl']: losses += 1
                    elif row['Low'].iloc[0] <= t['tp1']: wins += 1
                    else: new_open_trades.append(t)
            open_trades = new_open_trades
            
            trend = 'Uptrend' if row['EMA50'].iloc[0] > row['EMA200'].iloc[0] else 'Downtrend'
            structure = 'Bullish' if row['Close'].iloc[0] > row['EMA50'].iloc[0] else 'Bearish'
            adx = row['ADX'].iloc[0]
            
            local_dir = 'NO_TRADE'
            if trend == 'Uptrend' and structure == 'Bullish' and adx > 25: local_dir = 'BUY'
            elif trend == 'Downtrend' and structure == 'Bearish' and adx > 25: local_dir = 'SELL'
            
            if local_dir != 'NO_TRADE' and len(open_trades) == 0:
                p = row['Close'].iloc[0]
                atr = row['ATR'].iloc[0]
                tp1 = p + (atr*1.5) if local_dir == 'BUY' else p - (atr*1.5)
                sl = p - (atr*1.5) if local_dir == 'BUY' else p + (atr*1.5)
                open_trades.append({'type': local_dir, 'entry': p, 'tp1': tp1, 'sl': sl})
                
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 50.0
        return jsonify({'status': 'success', 'winRate': round(win_rate, 2), 'trades': wins+losses})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    print(f"MarketPulse FX TradingView Server running on http://0.0.0.0:2200")
    app.run(host='0.0.0.0', port=2200, debug=False)

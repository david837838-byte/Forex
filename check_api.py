import urllib.request
import json

try:
    resp = urllib.request.urlopen('http://127.0.0.1:5000/api/prices')
    data = json.loads(resp.read().decode('utf-8'))
    print("--- SERVER API OUTPUT ---")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error querying server: {e}")

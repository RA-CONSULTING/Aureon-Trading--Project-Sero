import requests, json
from datetime import datetime, timezone

url = 'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json'
resp = requests.get(url, timeout=10)
data = resp.json()

print(f'Total entries: {len(data)}')
print(f'First entry:')
print(json.dumps(data[0], indent=2))
print(f'Last entry:')
print(json.dumps(data[-1], indent=2))
print(f'Current UTC: {datetime.now(timezone.utc).isoformat()}')

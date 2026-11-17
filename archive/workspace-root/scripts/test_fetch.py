#!/usr/bin/env python3
import urllib.request, json, ssl

# TLS verification enabled — certificates verified against the system trust store.
ctx = ssl.create_default_context()

try:
    req = urllib.request.Request(
        'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
        headers={'User-Agent': 'HNC-Test/1.0'}
    )
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        text = resp.read().decode()
        data = json.loads(text)
        print('SUCCESS:', len(data), 'entries')
        print('LATEST:', data[-1])
except Exception as e:
    print('ERROR:', type(e).__name__, str(e))

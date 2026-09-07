import requests
import json

# Auth
resp = requests.post(
    "https://api-capital.backend-capital.com/api/v1/session",
    json={"identifier": "gary@raconsultingandbrokerageservices.com", "password": "Trekkers1@"},
    headers={"X-CAP-API-KEY": "N46xjejM9lhRmOyP", "Content-Type": "application/json"}
)
cst = resp.headers.get("CST")
xsec = resp.headers.get("X-SECURITY-TOKEN")

# Search for NATURALGAS
search = requests.get(
    "https://api-capital.backend-capital.com/api/v1/markets",
    params={"searchTerm": "NATURALGAS", "pageSize": 10},
    headers={"X-CAP-API-KEY": "N46xjejM9lhRmOyP", "CST": cst, "X-SECURITY-TOKEN": xsec}
)
print("Search status:", search.status_code)
data = search.json()
if "markets" in data:
    for m in data["markets"]:
        print(f"  {m.get('epic')} | {m.get('instrumentName')} | {m.get('symbol')}")

# Also try just getting the market directly
market = requests.get(
    "https://api-capital.backend-capital.com/api/v1/markets/NATURALGAS",
    headers={"X-CAP-API-KEY": "N46xjejM9lhRmOyP", "CST": cst, "X-SECURITY-TOKEN": xsec}
)
print("\nDirect market status:", market.status_code)
print(market.text[:500])

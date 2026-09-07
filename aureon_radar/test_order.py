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

# Test placing a small order
payload = {
    "epic": "NATURALGAS",
    "direction": "BUY",
    "size": 0.01,
    "orderType": "MARKET",
    "guaranteedStop": False,
    "forceOpen": True,
    "currencyCode": "GBP"
}

order = requests.post(
    "https://api-capital.backend-capital.com/api/v1/positions",
    json=payload,
    headers={"X-CAP-API-KEY": "N46xjejM9lhRmOyP", "CST": cst, "X-SECURITY-TOKEN": xsec, "Content-Type": "application/json"}
)
print("Order status:", order.status_code)
print(order.text[:500])

import requests

r = requests.post(
    "http://localhost:8000/buy-with-tp",
    json={"symbol": "AAPL", "qty": 1}
)

print(r.status_code)
print(r.json())

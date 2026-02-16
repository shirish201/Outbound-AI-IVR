from ib_insync import *
import math

SYMBOL = 'AAPL'
QTY = 10
PROFIT_PCT = 0.04
PORT = 7497
CLIENT_ID = 1

util.startLoop()

ib = IB()
ib.connect('127.0.0.1', PORT, clientId=CLIENT_ID)

contract = Stock(SYMBOL, 'SMART', 'USD')
ib.qualifyContracts(contract)

# ---- MARKET BUY ----
buy_order = MarketOrder(
    'BUY',
    QTY,
    tif='DAY',
    outsideRth=False
)

trade = ib.placeOrder(contract, buy_order)

while trade.orderStatus.status not in ('Filled', 'Cancelled'):
    ib.waitOnUpdate()

if trade.orderStatus.status != 'Filled':
    raise RuntimeError(f"BUY order failed: {trade.orderStatus.status}")

fill_price = trade.orderStatus.avgFillPrice

if fill_price <= 0:
    raise RuntimeError("Invalid avgFillPrice")

# ---- TAKE PROFIT ----
target_price = round(fill_price * (1 + PROFIT_PCT), 2)

sell_order = LimitOrder(
    'SELL',
    QTY,
    target_price,
    tif='GTC'   # recommended for TP
)

ib.placeOrder(contract, sell_order)

print(f"BUY filled at {fill_price}")
print(f"SELL limit placed at {target_price}")

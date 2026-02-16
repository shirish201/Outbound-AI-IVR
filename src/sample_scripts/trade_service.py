# trade_service.py
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
import threading
from ib_insync import IB, Stock, MarketOrder, LimitOrder
import nest_asyncio

# -----------------------------
# Patch asyncio for AnyIO (FastAPI)
# -----------------------------
nest_asyncio.apply()

# -----------------------------
# FastAPI setup
# -----------------------------
app = FastAPI(title="IBKR Trade Service")

class TradeRequest(BaseModel):
    symbol: str
    qty: int
    profit_pct: float = 0.04

# -----------------------------
# IBKR setup in a separate thread
# -----------------------------
ib = IB()
ib_loop = asyncio.new_event_loop()

def start_ib_loop():
    asyncio.set_event_loop(ib_loop)
    ib_loop.run_until_complete(
        ib.connectAsync('127.0.0.1', 7497, clientId=7)
    )
    ib_loop.run_forever()

threading.Thread(target=start_ib_loop, daemon=True).start()

# -----------------------------
# Helper to run coroutine in IBKR loop
# -----------------------------
def run_ib(coro):
    fut = asyncio.run_coroutine_threadsafe(coro, ib_loop)
    return fut.result(timeout=30000)  # optional timeout

# -----------------------------
# Async helper to place order + wait fill
# -----------------------------
async def place_buy_with_tp(symbol: str, qty: int, profit_pct: float = 0.04):
    contract = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)

    # Market BUY
    buy_order = MarketOrder('BUY', qty, tif='DAY', outsideRth=False)
    trade = ib.placeOrder(contract, buy_order)

    # Wait for fill using asyncio.Event
    filled_event = asyncio.Event()

    def on_fill(t):
        filled_event.set()

    trade.filledEvent += on_fill
    await filled_event.wait()  # ✅ this is now a real coroutine

    fill_price = trade.orderStatus.avgFillPrice
    target_price = round(fill_price * (1 + profit_pct), 2)

    # Place LIMIT SELL
    sell_order = LimitOrder('SELL', qty, target_price, tif='GTC')
    ib.placeOrder(contract, sell_order)

    return {
        "symbol": symbol,
        "qty": qty,
        "fill_price": fill_price,
        "target_price": target_price,
        "status": "BUY filled, SELL placed"
    }

# -----------------------------
# FastAPI endpoint
# -----------------------------
@app.post("/buy-with-tp")
def buy_with_tp(req: TradeRequest):
    try:
        result = run_ib(place_buy_with_tp(req.symbol, req.qty, req.profit_pct))
        return result
    except Exception as e:
        return {"error": str(e)}

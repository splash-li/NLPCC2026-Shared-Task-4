from fastapi import APIRouter, Depends, HTTPException
from .agents import get_current_user
import asyncio
import random
from datetime import datetime

router = APIRouter()

# In-memory store for live trading sessions and data
live_sessions = {}
market_data_feed = {}

async def market_data_simulator():
    """Simulates a live market data feed."""
    while True:
        for fund_id in market_data_feed:
            # Simulate price changes
            price = market_data_feed[fund_id]["price"]
            change = random.uniform(-0.5, 0.5)
            market_data_feed[fund_id]["price"] = round(price + change, 2)
        await asyncio.sleep(5) # Update every 5 seconds

@router.on_event("startup")
async def startup_event():
    # Initialize some dummy market data
    market_data_feed["FUND001"] = {"price": 150.0}
    market_data_feed["FUND002"] = {"price": 200.0}
    market_data_feed["FUND003"] = {"price": 120.0}
    asyncio.create_task(market_data_simulator())

@router.post("/start")
def start_live_trading(current_user: dict = Depends(get_current_user)):
    session_id = str(random.randint(1000, 9999))
    live_sessions[session_id] = {
        "user": current_user["username"],
        "capital": 1000000,
        "portfolio": {fund_id: 0 for fund_id in market_data_feed},
        "transaction_history": []
    }
    return {"session_id": session_id}

@router.get("/market_data")
def get_market_data(current_user: dict = Depends(get_current_user)):
    return market_data_feed

@router.post("/{session_id}/trade")
def submit_live_trade(session_id: str, trade: dict, current_user: dict = Depends(get_current_user)):
    if session_id not in live_sessions:
        raise HTTPException(status_code=404, detail="Live session not found")
    
    session = live_sessions[session_id]
    fund_id = trade["fund_id"]
    action = trade["action"]
    quantity = trade["quantity"]
    price = market_data_feed[fund_id]["price"]

    if action == "buy":
        cost = price * quantity
        commission = cost * 0.0001
        if session["capital"] >= cost + commission:
            session["capital"] -= (cost + commission)
            session["portfolio"][fund_id] += quantity
            session["transaction_history"].append(trade)
    elif action == "sell":
        if session["portfolio"][fund_id] >= quantity:
            revenue = price * quantity
            commission = revenue * 0.0001
            session["capital"] += (revenue - commission)
            session["portfolio"][fund_id] -= quantity
            session["transaction_history"].append(trade)
            
    return session